"""OMA orthology tool showing a MCP Apps widget, calling the OMA browser API (https://omabrowser.org/api) directly.

`show_gene_family` shows the history of the gene family of a protein, from its Hierarchical Orthologous Group (HOG):
the species tree with the duplications and losses of each clade and the genes of each species, like the iHam viewer,
with its pairwise orthologs, and its gene neighbourhood conserved across species, like the OMA local synteny viewer.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from defusedxml import ElementTree as SafeET
from mcp.server.apps import ResourceCsp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from typing_extensions import TypedDict

from sparql_llm.uniprot_tools import CDN, apps, get, http_client, text_result, widget_html

OMA_API = "https://omabrowser.org/api"
OMA_WEB = "https://omabrowser.org"
NS = "{http://orthoXML.org/2011/}"
# Species shown in the gene neighbourhood first, when they have a 1:1 ortholog
SYNTENY_SPECIES = ["MOUSE", "BOVIN", "MONDO", "CHICK", "XENTR", "DANRE", "DROME", "CAEEL", "YEAST", "ARATH"]
MAX_SYNTENY = 8
# OrthoXML of families spanning the tree of life are tens of MB
MAX_ORTHOXML = 15_000_000
# UniProt entry names, e.g. P53_HUMAN, not RefSeq IDs like NP_000537
UNIPROT_NAME = re.compile(r"^([A-Z0-9]{1,10})_([A-Z0-9]{3,5})$")


# Data sent to the widget in `structuredContent`, as read by `widgets/oma.html`
class FamilyGene(TypedDict):
    omaid: str
    lineage: str
    """Sub-HOG of the gene: the paralog lineage after the duplications, e.g. HOG:F0782425.2c.7a"""
    name: str | None
    rel: str | None
    """Orthology with the protein shown: 1:1, 1:n, m:1, m:n, or self"""


class TaxonNode(TypedDict):
    id: str
    name: str
    groups: list[str]
    """Ancestral genes of the family in this clade, by lineage"""
    dups: int
    """Duplications in this clade"""
    losses: list[str]
    """Lineages lost when going from the parent clade to this one"""
    genes: list[FamilyGene]
    count: int
    """Genes of the family in the clade"""
    children: list["TaxonNode"]


class SyntenyGene(TypedDict):
    id: str
    name: str | None
    description: str | None
    family: str
    """Root HOG, the color of the gene across species"""
    strand: str
    start: int
    end: int


class SyntenyRow(TypedDict):
    species: str
    code: str
    focus: str
    """The protein or its ortholog in this species, the rows are aligned on it"""
    chromosome: str | None
    genes: list[SyntenyGene]


class FamilyData(TypedDict):
    protein: dict[str, Any]
    hog: str
    rootLevel: str | None
    tree: TaxonNode | None
    orthologs: dict[str, int]
    """Number of orthologs by type, 1:1, 1:n..."""
    synteny: list[SyntenyRow]


async def oma(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    res = await get(client, f"{OMA_API}/{path}", params)
    if res.status_code == 404:
        raise ToolError(f"Not found in OMA: {path} {res.text[:200]}")
    if res.status_code != 200:
        raise ToolError(f"OMA API error {res.status_code}: {res.text[:300]}")
    return res.json()


async def fetch_protein(client: httpx.AsyncClient, query: str) -> dict[str, Any]:
    """OMA protein of a UniProt accession, UniProt entry name, OMA ID or Ensembl ID, its main isoform when it is
    another one, as only main isoforms are in HOGs"""
    p = await oma(client, f"protein/{query.strip()}/")
    if p.get("is_main_isoform") is False:
        isoforms = await oma(client, f"protein/{p['entry_nr']}/isoforms/")
        main = next((i for i in isoforms if i.get("is_main_isoform")), None)
        if main:
            p = await oma(client, f"protein/{main['entry_nr']}/")
    return p


def gene_name(p: dict[str, Any]) -> str | None:
    """Short name, e.g. P53 from P53_HUMAN, or the start of the description"""
    canonical = p.get("canonicalid") or ""
    if m := UNIPROT_NAME.match(canonical):
        return m[1]
    return description_of(p)[:40] or canonical or None


def description_of(p: dict[str, Any]) -> str:
    """Description without its source and transcript, e.g. tumor protein p53"""
    description = (p.get("description") or "").split(" [")[0].split(";")[0].strip()
    return "" if description.startswith("transcript_id=") else description


def parse_family(xml: str, names: dict[str, dict[str, Any]]) -> tuple[TaxonNode | None, str | None]:
    """Species tree of a HOG with its ancestral genes, duplications, losses and genes, from the OMA augmented OrthoXML"""
    # Parsed without entities, the OrthoXML comes from the network
    root = SafeET.fromstring(xml)
    # Genes: OrthoXML IDs to OMA IDs
    omaids = {g.get("id", ""): g.get("protId", "") for g in root.iter(f"{NS}gene")}
    # Taxonomy, with the ancestors of each taxon to place losses when OMA skips intermediate levels
    nodes: dict[str, TaxonNode] = {}
    ancestors: dict[str, set[str]] = {}

    def add_taxon(t: ET.Element, parents: set[str]) -> TaxonNode:
        tid = t.get("id", "")
        ancestors[tid] = parents
        node = TaxonNode(id=tid, name=t.get("name", ""), groups=[], dups=0, losses=[], genes=[], count=0, children=[])
        nodes[tid] = node
        node["children"] = [add_taxon(c, parents | {tid}) for c in t.findall(f"{NS}taxon")]
        return node

    tax_root = root.find(f"{NS}taxonomy/{NS}taxon")
    if tax_root is None:
        return None, None
    tree = add_taxon(tax_root, set())

    def visit(og: ET.Element) -> None:
        taxon = og.get("taxonId", "")
        lineage = og.get("id", "").split("_")[0]
        node = nodes.get(taxon)
        if node is None:
            return
        node["groups"].append(lineage)
        present: set[str] = set()

        def add_children(parent: ET.Element) -> None:
            for ch in parent:
                tag = ch.tag.removeprefix(NS)
                if tag == "orthologGroup":
                    present.add(ch.get("taxonId", ""))
                    visit(ch)
                elif tag == "paralogGroup":
                    node["dups"] += 1
                    add_children(ch)
                elif tag == "geneRef":
                    omaid = omaids.get(ch.get("id", ""), ch.get("id", ""))
                    p = names.get(omaid, {})
                    node["genes"].append(
                        FamilyGene(omaid=omaid, lineage=ch.get("LOFT", lineage), name=p.get("name"), rel=p.get("rel"))
                    )

        add_children(og)
        # Lost in a child clade when no group or gene of the lineage is in it or below it
        if node["children"] and not node["genes"]:
            for child in node["children"]:
                if not any(t == child["id"] or child["id"] in ancestors.get(t, set()) for t in present):
                    child["losses"].append(lineage)

    for og in root.findall(f"{NS}groups/{NS}orthologGroup"):
        visit(og)

    def count(n: TaxonNode) -> int:
        n["count"] = len(n["genes"]) + sum(count(c) for c in n["children"])
        return n["count"]

    count(tree)
    return tree, tree["name"]


async def fetch_synteny(client: httpx.AsyncClient, proteins: list[dict[str, Any]]) -> list[SyntenyRow]:
    """Neighbours of the gene and of its orthologs in their genomes, 3 genes on each side"""

    async def neighbours(p: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return await oma(client, f"synteny/{p['omaid']}/", {"level": p["species"]["code"], "context": 3})
        except ToolError:
            return None

    graphs = await asyncio.gather(*[neighbours(p) for p in proteins])
    ids = sorted({n["id"] for g in graphs if g for n in g.get("nodes", [])})
    info: dict[str, dict[str, Any]] = {}
    if ids:
        res = await client.post(f"{OMA_API}/protein/bulk_retrieve/", json={"ids": ids})
        if res.status_code == 200:
            info = {x["query_id"]: x.get("target") or {} for x in res.json()}
    rows = []
    for p, g in zip(proteins, graphs, strict=True):
        if not g:
            continue
        genes = sorted(g.get("nodes", []), key=lambda n: n.get("start", 0))
        rows.append(
            SyntenyRow(
                species=p["species"]["species"],
                code=p["species"]["code"],
                focus=p["omaid"],
                chromosome=next((n.get("chromosome") for n in genes if n["id"] == p["omaid"]), None),
                genes=[
                    SyntenyGene(
                        id=n["id"],
                        name=gene_name(info.get(n["id"], {})),
                        description=description_of(info.get(n["id"], {})) or None,
                        family=(n.get("hog_id") or n["id"]).split(".")[0],
                        strand=n.get("strand", "+"),
                        start=n.get("start", 0),
                        end=n.get("end", 0),
                    )
                    for n in genes
                ],
            )
        )
    return rows


@apps.tool(resource_uri="ui://oma/oma.html")
async def show_gene_family(protein: str) -> CallToolResult:
    """Show the history of the gene family of a protein from the OMA orthology database to the user: the species tree
    of its Hierarchical Orthologous Group (HOG) with the duplications and losses in each clade and the genes of each
    species colored by paralog lineage (like the OMA iHam viewer), its pairwise orthologs (1:1, 1:n...), and its gene
    neighbourhood conserved in other species (local synteny). `protein` is a UniProt accession (e.g. P04637), a UniProt
    entry name (P53_HUMAN), an OMA ID (HUMAN31534) or an Ensembl ID"""
    async with http_client() as client:
        p = await fetch_protein(client, protein)
        if not p.get("oma_hog_id"):
            raise ToolError(f"{p.get('omaid')} ({p.get('canonicalid')}) is not part of any OMA HOG")
        root_hog = p["oma_hog_id"].split(".")[0]
        orthologs, xml = await asyncio.gather(
            oma(client, f"protein/{p['entry_nr']}/orthologs/"),
            get(client, f"{OMA_WEB}/oma/hog/{root_hog}/orthoxml/augmented/"),
        )
        # Gene neighbourhood in the species of the protein and in species with a 1:1 ortholog
        one_to_one = {o["species"]["code"]: o for o in orthologs if o.get("rel_type") == "1:1"}
        picked = [one_to_one[c] for c in SYNTENY_SPECIES if c in one_to_one and c != p["species"]["code"]]
        picked += [o for c, o in one_to_one.items() if o not in picked][: max(0, MAX_SYNTENY - len(picked))]
        synteny = await fetch_synteny(client, [p, *picked[:MAX_SYNTENY]])

    names = {o["omaid"]: {"name": gene_name(o), "rel": o.get("rel_type")} for o in orthologs}
    names[p["omaid"]] = {"name": gene_name(p), "rel": "self"}
    tree, root_level = (None, None)
    if xml.status_code == 200 and len(xml.content) <= MAX_ORTHOXML:
        tree, root_level = await asyncio.to_thread(parse_family, xml.text, names)
    rels: dict[str, int] = {}
    for o in orthologs:
        rels[o.get("rel_type", "?")] = rels.get(o.get("rel_type", "?"), 0) + 1
    info = {
        "omaid": p["omaid"],
        "entry": p["entry_nr"],
        "name": gene_name(p),
        "canonicalid": p.get("canonicalid"),
        "description": description_of(p),
        "species": p["species"]["species"],
        "taxId": str(p["species"]["taxon_id"]),
        "code": p["species"]["code"],
        "hogLevels": p.get("hog_levels", []),
        "length": p.get("sequence_length"),
    }
    data = FamilyData(
        protein=info, hog=p["oma_hog_id"], rootLevel=root_level, tree=tree, orthologs=rels, synteny=synteny
    )

    # Summary for the model: clades with duplications or losses
    events: list[str] = []

    def walk(n: TaxonNode) -> None:
        if n["dups"] or n["losses"]:
            parts = [
                f"{n['dups']} duplications" if n["dups"] else "",
                f"{len(n['losses'])} losses" if n["losses"] else "",
            ]
            events.append(f"{n['name']}: {', '.join(x for x in parts if x)}, {n['count']} genes")
        for c in n["children"]:
            walk(c)

    if tree:
        walk(tree)
    lines = [
        f"Shown to the user: OMA gene family of {info['omaid']} {info['canonicalid']} ({info['description']}, "
        f"{info['species']}), HOG {data['hog']}, family rooted at {root_level}",
        f"{tree['count'] if tree else '?'} genes in the HOG. Orthologs: "
        + ", ".join(f"{k}: {v}" for k, v in sorted(rels.items())),
        "Duplications and losses by clade:" if events else "No duplication or loss",
        *[f"- {e}" for e in events[:60]],
        "Gene neighbourhood (3 genes on each side): "
        + "; ".join(f"{r['code']}: {' '.join(g['name'] or g['id'] for g in r['genes'])}" for r in synteny),
    ]
    if not tree:
        lines.append("The HOG is too large to show its species tree, only the orthologs and synteny are shown")
    lines.append("The user can expand clades, click genes and events, and compare the gene neighbourhoods.")
    return text_result("\n".join(lines), data)


apps.add_html_resource(
    "ui://oma/oma.html",
    widget_html("oma.html"),
    title="OMA gene family",
    csp=ResourceCsp(resource_domains=[CDN]),
)
