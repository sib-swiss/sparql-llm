"""Rhea reaction tool showing a MCP Apps widget, calling the Rhea website API (https://www.rhea-db.org) directly.

`show_reaction` shows the equation with the structures of the participants, and the atom map of the reaction drawn by
Rhea (CDK depiction of the RXNMapper mapping), with its EC numbers, directions, cross-references and reviewed enzymes.
"""

import asyncio
import base64
import re
from typing import Any

import httpx
from mcp.server.apps import ResourceCsp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from typing_extensions import TypedDict

from sparql_llm.uniprot_tools import (
    CDN,
    UNIPROT_API,
    SearchRow,
    apps,
    get,
    http_client,
    search_row,
    text_result,
    widget_html,
)

RHEA = "https://www.rhea-db.org"
RHEA_ID = re.compile(r"^\s*(?:rhea:)?(\d+)\s*$", re.IGNORECASE)
MAX_ENZYMES = 200


# Data sent to the widget in `structuredContent`, as read by `widgets/reaction.html`
class Participant(TypedDict):
    id: str
    """e.g. CHEBI:15377, or RHEA-COMP:9565 for generic compounds and polymers"""
    name: str
    """As written in the equation"""
    chebiName: str | None
    type: str
    """SMALL_MOLECULE, GENERIC_COMPOUND or POLYMER"""
    coef: str | None
    formula: str | None
    charge: int | None
    smiles: str | None
    inchikey: str | None
    image: str | None
    """SVG depiction as a data URI"""


class Direction(TypedDict):
    id: str
    direction: str
    equation: str


class Xref(TypedDict):
    type: str
    id: str
    url: str | None
    label: str | None


class ReactionData(TypedDict):
    id: str
    equation: str
    direction: str
    """none for the undefined direction (master reaction), forward, backward or bi"""
    status: str
    balanced: bool
    transport: bool
    left: list[Participant]
    right: list[Participant]
    ec: list[Xref]
    directions: list[Direction]
    xrefs: list[Xref]
    pubmed: list[str]
    atomMap: str | None
    """SVG of the reaction with the atoms of each reactant colored in the products, without scripts"""
    confidence: float | None
    """RXNMapper confidence of the atom map"""
    enzymes: list[SearchRow]
    """Reviewed UniProtKB entries catalyzing the reaction"""
    reviewedTotal: int
    unreviewedTotal: int


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def clean_svg(svg: str) -> str:
    """SVG to inline in the widget: no XML prolog, scripts or event handlers"""
    svg = svg[svg.find("<svg") :]
    svg = re.sub(r"<script[\s\S]*?</script>", "", svg, flags=re.IGNORECASE)
    return re.sub(r"\son\w+\s*=\s*(['\"]).*?\1", "", svg)


def svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(clean_svg(svg).encode()).decode()


async def find_reaction(client: httpx.AsyncClient, query: str) -> tuple[str, list[str]]:
    """Rhea ID from an ID or a search (e.g. `ec:2.7.11.1`, `chebi:15422`, `uniprot:P31749` or text), with the
    other hits"""
    if m := RHEA_ID.match(query):
        return m[1], []
    res = await get(
        client, f"{RHEA}/rhea", {"query": query, "columns": "rhea-id,equation", "format": "tsv", "limit": 10}
    )
    res.raise_for_status()
    hits = [line.split("\t") for line in res.text.splitlines()[1:] if line.strip()]
    if not hits:
        raise ToolError(f"No Rhea reaction found for {query!r}")
    return hits[0][0].removeprefix("RHEA:"), [f"{h[0]} {h[1]}" for h in hits[1:]]


async def participant(client: httpx.AsyncClient, p: dict[str, Any]) -> Participant:
    """Participant with its structure, polymers and generic compounds use the image of their reactive part"""
    image = None
    if p.get("thumbnail"):
        res = await get(client, f"{RHEA}{p['thumbnail']}")
        if res.status_code == 200 and "svg" in res.headers.get("content-type", ""):
            image = svg_data_uri(res.text)
    prefix = "CHEBI" if p.get("idprefix") == "chebi" else str(p.get("idprefix", "")).upper()
    return Participant(
        id=f"{prefix}:{p['id']}",
        name=strip_html(p.get("htmlname") or p.get("label", "")),
        chebiName=p.get("label"),
        type=p.get("type", ""),
        coef=p.get("coff"),
        formula=p.get("formula"),
        charge=p.get("charge"),
        smiles=p.get("smiles"),
        inchikey=p.get("inchikey"),
        image=image,
    )


async def enzymes(client: httpx.AsyncClient, rhea_id: str) -> tuple[list[SearchRow], int, int]:
    """Reviewed UniProtKB entries catalyzing the reaction, and the reviewed and unreviewed counts"""
    fields = "accession,id,protein_name,gene_primary,organism_name,reviewed,annotation_score,length"
    reviewed, unreviewed = await asyncio.gather(
        get(
            client,
            f"{UNIPROT_API}/search",
            {"query": f"rhea:{rhea_id} AND reviewed:true", "fields": fields, "size": MAX_ENZYMES},
        ),
        get(client, f"{UNIPROT_API}/search", {"query": f"rhea:{rhea_id} AND reviewed:false", "size": 0}),
    )
    if reviewed.status_code != 200:
        return [], 0, 0
    rows = [search_row(e) for e in reviewed.json()["results"]]
    return rows, int(reviewed.headers.get("x-total-results", 0)), int(unreviewed.headers.get("x-total-results", 0))


def xrefs_of(groups: list[dict[str, Any]]) -> list[Xref]:
    return [
        Xref(type=g["type"], id=x["id"], url=x.get("url"), label=x.get("label"))
        for g in groups
        for x in g.get("entries", [])
    ]


def side_text(ps: list[Participant]) -> str:
    return " + ".join(f"{p['coef'] + ' ' if p['coef'] else ''}{p['name']} ({p['id']})" for p in ps)


@apps.tool(resource_uri="ui://rhea/reaction.html")
async def show_reaction(reaction: str) -> CallToolResult:
    """Show a Rhea biochemical reaction to the user: its atom map (atoms of each reactant colored in the products,
    with atom numbers), the equation with the structures of the participants, EC numbers, directions,
    cross-references (GO, KEGG, MetaCyc, Reactome, M-CSA) and the reviewed UniProtKB enzymes catalyzing it.
    `reaction` is a Rhea ID (e.g. RHEA:10000 or 10000) or a Rhea search (e.g. `ec:2.7.11.1`, `chebi:15422`,
    `uniprot:P31749`, or text), showing the first hit"""
    async with http_client() as client:
        rhea_id, others = await find_reaction(client, reaction)
        res, svg = await asyncio.gather(
            get(client, f"{RHEA}/rhea/{rhea_id}/json"), get(client, f"{RHEA}/rhea/{rhea_id}/svg")
        )
        if res.status_code != 200 or not res.headers.get("content-type", "").startswith("application/json"):
            raise ToolError(f"Rhea reaction {rhea_id} not found")
        r = res.json()
        left, right, (enzyme_rows, reviewed, unreviewed) = await asyncio.gather(
            asyncio.gather(*[participant(client, p) for p in r.get("left", [])]),
            asyncio.gather(*[participant(client, p) for p in r.get("right", [])]),
            enzymes(client, rhea_id),
        )
    atom_map = clean_svg(svg.text) if svg.status_code == 200 and "<svg" in svg.text else None
    confidence = re.search(r'data-confidence="([\d.]+)"', atom_map or "")
    data = ReactionData(
        id=f"RHEA:{rhea_id}",
        equation=r["equation"],
        direction=r.get("direction", "none"),
        status=r.get("status", ""),
        balanced=bool(r.get("balanced")),
        transport=bool(r.get("transport")),
        left=list(left),
        right=list(right),
        ec=[Xref(type="EC", id=e["id"], url=e.get("url"), label=e.get("label")) for e in r.get("ec", [])],
        directions=[
            Direction(id=f"RHEA:{d['id']}", direction=d["direction"], equation=d["equation"])
            for d in r.get("otherdirections", [])
        ],
        xrefs=xrefs_of(r.get("crossref", [])),
        pubmed=[x["id"] for c in r.get("citations", []) if c.get("type") == "pubmed" for x in c.get("entries", [])],
        atomMap=atom_map,
        confidence=float(confidence[1]) if confidence else None,
        enzymes=enzyme_rows,
        reviewedTotal=reviewed,
        unreviewedTotal=unreviewed,
    )

    # Summary for the model
    ec = ", ".join(f"{e['id']} {e['label']}" for e in data["ec"])
    directions = "; ".join(f"{d['id']} {d['direction']}" for d in data["directions"])
    xrefs = "; ".join(f"{x['type']} {x['id']}" for x in data["xrefs"][:20])
    lines = [
        f"Shown to the user: Rhea reaction {data['id']} ({data['status']}, direction: {data['direction']}"
        f"{', transport' if data['transport'] else ''}{'' if data['balanced'] else ', not balanced'})",
        f"Equation: {data['equation']}",
        f"Left: {side_text(data['left'])}",
        f"Right: {side_text(data['right'])}",
        f"EC: {ec or 'none'}",
        "Atom map: "
        + (f"shown, RXNMapper confidence {data['confidence']}" if atom_map else "not available (e.g. polymers)"),
        f"Other directions: {directions or 'none'}",
        f"Cross-references: {xrefs or 'none'}",
        f"PubMed: {', '.join(data['pubmed'][:15]) or 'none'}",
        f"Enzymes in UniProtKB: {reviewed} reviewed, {unreviewed} unreviewed. Reviewed: "
        + "; ".join(f"{e['accession']} {e['gene'] or e['id']} ({e['organism']})" for e in enzyme_rows[:25]),
    ]
    if others:
        lines.append(f"Other hits of the search, not shown: {'; '.join(others)}")
    lines.append(
        "The user can toggle the atom colors and numbers, and click participants and enzymes to ask about them."
    )
    return text_result("\n".join(lines), data)


apps.add_html_resource(
    "ui://rhea/reaction.html",
    widget_html("reaction.html"),
    title="Rhea reaction and atom map",
    csp=ResourceCsp(resource_domains=[CDN]),
)
