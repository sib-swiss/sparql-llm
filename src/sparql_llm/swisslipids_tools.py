"""SwissLipids tool showing a MCP Apps widget, calling the SwissLipids API (https://www.swisslipids.org/api/) and
its SPARQL endpoint for the hierarchy.

`show_lipid` shows a lipid in the SwissLipids hierarchy (category > class > species > molecular subspecies >
structural subspecies > isomeric subspecies), with its structure, Rhea reactions and enzymes, own and inherited from its
classes, and where it was found (tissues, cellular components).
"""

import asyncio
import re
from typing import Any

import httpx
from mcp.server.apps import ResourceCsp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from typing_extensions import TypedDict

from sparql_llm.uniprot_tools import CDN, READ_ONLY, apps, get, http_client, text_result, widget_html

SWISSLIPIDS_API = "https://www.swisslipids.org/api/index.php"
SWISSLIPIDS_SPARQL = "https://beta.sparql.swisslipids.org/sparql/"
SLM = "https://swisslipids.org/rdf/SLM_"
PREFIXES = """PREFIX SWISSLIPID: <https://swisslipids.org/rdf/SLM_>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
"""
SLM_ID = re.compile(r"^\s*SLM:?(\d+)\s*$", re.IGNORECASE)
MAX_CHILDREN = 60
MAX_REACTIONS = 300


# Data sent to the widget in `structuredContent`, as read by `widgets/lipid.html`
class HierarchyNode(TypedDict):
    id: str
    name: str
    level: str | None
    """Category, Class, Species, Molecular subspecies, Structural subspecies or Isomeric subspecies"""


class Edge(TypedDict):
    child: str
    parent: str


class LipidReaction(TypedDict):
    rhea: str
    direction: str
    equation: str
    participants: list[HierarchyNode]
    enzymes: list[dict[str, str | None]]
    """UniProtKB accession, gene or protein name, organism and taxon ID"""
    inheritedFrom: HierarchyNode | None
    """Class of the lipid the reaction is described for"""


class Location(TypedDict):
    kind: str
    """Tissue or cellular component"""
    id: str
    name: str
    taxa: list[str]
    pubmed: list[str]


class LipidData(TypedDict):
    id: str
    name: str
    abbreviation: str | None
    definition: str | None
    level: str | None
    formula: str | None
    mass: float | None
    charge: int | None
    smiles: str | None
    inchikey: str | None
    depiction: str | None
    """PNG data URI"""
    synonyms: list[str]
    xrefs: list[dict[str, str]]
    components: list[dict[str, str]]
    """Chains of the lipid, e.g. sn1 and sn2"""
    lineage: list[HierarchyNode]
    edges: list[Edge]
    """Parent links of the lineage of the lipid, up to the Lipid root"""
    children: list[HierarchyNode]
    childrenTotal: int
    reactions: list[LipidReaction]
    locations: list[Location]


def clean(name: str | None) -> str:
    """Name without the SwissLipids markup, e.g. <stereo>L</stereo>"""
    return re.sub(r"<[^>]+>", "", name or "").strip()


def slm(iri: str) -> str:
    return iri.replace(SLM, "SLM:")


def level_of(iri: str | None) -> str | None:
    return iri.replace(SLM, "").replace("_", " ").capitalize() if iri else None


async def swisslipids(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    res = await get(client, f"{SWISSLIPIDS_API}/{path}", params)
    if res.status_code != 200:
        raise ToolError(f"SwissLipids API error {res.status_code}: {res.text[:300]}")
    return res.json()


async def sparql(client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
    res = await client.post(
        SWISSLIPIDS_SPARQL, data={"query": PREFIXES + query}, headers={"Accept": "application/sparql-results+json"}
    )
    if res.status_code != 200:
        raise ToolError(f"SwissLipids SPARQL endpoint error {res.status_code}: {res.text[:300]}")
    return [{k: v["value"] for k, v in b.items()} for b in res.json()["results"]["bindings"]]


async def find_lipid(client: httpx.AsyncClient, query: str) -> tuple[str, list[str]]:
    """SwissLipids ID from an ID or a search by name, abbreviation (e.g. PC(16:0/18:1)) or ChEBI ID, exact names
    first as the search results are not ranked"""
    if m := SLM_ID.match(query):
        return f"SLM:{m[1]}", []
    # The search answers 404 when nothing matches
    res = await get(client, f"{SWISSLIPIDS_API}/search", {"term": query.strip()})
    hits = [h for h in res.json() if h.get("entity_type") == "metabolite"] if res.status_code == 200 else []
    if not hits:
        raise ToolError(
            f"No SwissLipids lipid found for {query!r}: the search only matches SwissLipids names and abbreviations, "
            "not all synonyms. Try the ChEBI ID of the lipid (e.g. CHEBI:17759 for 7-dehydrocholesterol) or its "
            "systematic name (e.g. cholesta-5,7-dien-3beta-ol)"
        )
    q = query.strip().lower()
    hits.sort(key=lambda h: (clean(h["entity_name"]).lower() != q, q not in h["entity_name"].lower()))
    return hits[0]["entity_id"], [f"{h['entity_id']} {clean(h['entity_name'])}" for h in hits[1:8]]


async def fetch_hierarchy(
    client: httpx.AsyncClient, lipid_id: str
) -> tuple[list[HierarchyNode], list[Edge], list[HierarchyNode], int, str | None, str | None]:
    """Lineage of the lipid as a graph, its direct children, their number, its depiction and level"""
    iri = f"<{SLM}{lipid_id.removeprefix('SLM:')}>"
    lineage, children, count, entity = await asyncio.gather(
        sparql(
            client,
            f"""SELECT ?child ?parent ?label ?rank WHERE {{
              {iri} rdfs:subClassOf* ?child . ?child rdfs:subClassOf ?parent .
              ?parent rdfs:label ?label OPTIONAL {{ ?parent SWISSLIPID:rank ?rank }}
            }}""",
        ),
        sparql(
            client,
            f"""SELECT ?c ?label ?rank WHERE {{
              ?c rdfs:subClassOf {iri} ; rdfs:label ?label OPTIONAL {{ ?c SWISSLIPID:rank ?rank }}
            }} ORDER BY ?label LIMIT {MAX_CHILDREN}""",
        ),
        sparql(client, f"SELECT (COUNT(?c) AS ?n) WHERE {{ ?c rdfs:subClassOf {iri} }}"),
        sparql(
            client,
            f"""SELECT (STR(?d) AS ?depiction) ?rank WHERE {{
              OPTIONAL {{ {iri} foaf:depiction ?d }} OPTIONAL {{ {iri} SWISSLIPID:rank ?rank }}
            }} LIMIT 1""",
        ),
    )
    # Without the browsing groups, e.g. SLM_34C1DB "34 Carbons with 1 double bonds"
    lineage = [r for r in lineage if SLM_ID.match(slm(r["parent"])) and SLM_ID.match(slm(r["child"]))]
    nodes = {
        slm(r["parent"]): HierarchyNode(id=slm(r["parent"]), name=r["label"], level=level_of(r.get("rank")))
        for r in lineage
    }
    edges = [Edge(child=slm(r["child"]), parent=slm(r["parent"])) for r in lineage]
    kids = [HierarchyNode(id=slm(r["c"]), name=r["label"], level=level_of(r.get("rank"))) for r in children]
    depiction = entity[0].get("depiction") if entity else None
    level = level_of(entity[0].get("rank")) if entity else None
    return list(nodes.values()), edges, kids, int(count[0]["n"]) if count else 0, depiction, level


def reactions_of(reactions: dict[str, Any], inherited: HierarchyNode | None) -> list[LipidReaction]:
    out = []
    for r in reactions.values():
        rhea = r.get("reaction", {}).get("rhea") or {}
        if not rhea.get("rhea_id"):
            continue
        sides = [rhea.get("rhea_reactants") or {}, rhea.get("rhea_products") or {}]
        equation = f" {rhea.get('rhea_direction') or '='} ".join(
            " + ".join(
                f"{'' if p.get('stoichiometry') in (None, '1') else p['stoichiometry'] + ' '}{clean(p['name'])}"
                for p in side.values()
            )
            for side in sides
        )
        out.append(
            LipidReaction(
                rhea=rhea["rhea_id"],
                direction=rhea.get("rhea_direction") or "=",
                equation=equation,
                participants=[
                    HierarchyNode(id=p["id"], name=clean(p["name"]), level=None)
                    for side in sides
                    for p in side.values()
                ],
                enzymes=[
                    {
                        "accession": e.get("enzyme_uniprotkb_id"),
                        "name": e.get("enzyme_name"),
                        "organism": e.get("host"),
                        "taxId": e.get("tax_id"),
                    }
                    for e in r.get("enzymes") or []
                    if e.get("enzyme_uniprotkb_id")
                ],
                inheritedFrom=inherited,
            )
        )
    return out


def locations_of(summaries: list[dict[str, Any]]) -> list[Location]:
    out = []
    for s in summaries or []:
        if s.get("tissue_id"):
            kind, id_, name = "Tissue", s["tissue_id"], s.get("tissue")
        elif s.get("go_id") and s.get("go_namespace") in (None, "cellular_component"):
            kind, id_, name = "Cellular component", s["go_id"], s.get("go_name")
        else:
            continue
        taxa = s.get("taxa") or []
        out.append(
            Location(
                kind=kind,
                id=id_,
                name=name or id_,
                taxa=sorted({t["taxon"] for t in taxa if t.get("taxon")}),
                pubmed=sorted({e["reference"] for t in taxa for e in t.get("evidences") or [] if e.get("reference")}),
            )
        )
    return out


def none_if(v: str | None, *empty: str) -> str | None:
    return None if not v or v in empty else v


@apps.tool(resource_uri="ui://swisslipids/lipid.html", annotations=READ_ONLY)
async def show_lipid(query: str) -> CallToolResult:
    """Show a lipid of SwissLipids to the user: its place in the lipid hierarchy (category > class > species >
    molecular subspecies > structural subspecies > isomeric subspecies) as a graph with its parents and children,
    its structure and properties, its chains, the Rhea reactions it is involved in with their enzymes in UniProtKB,
    own and inherited from its classes, and the tissues and cellular components it was found in.
    `query` is a SwissLipids ID (e.g. SLM:000000651), a ChEBI ID (e.g. CHEBI:73001), a lipid name or an abbreviation
    (e.g. cholesterol, PC(16:0/18:1), Cer(d18:1/16:0)). Common names that are not SwissLipids names are not found,
    use the ChEBI ID for them"""
    async with http_client() as client:
        lipid_id, others = await find_lipid(client, query)
        e, (lineage, edges, children, total, depiction, level) = await asyncio.gather(
            swisslipids(client, f"entity/{lipid_id}"), fetch_hierarchy(client, lipid_id)
        )
    e = e[0] if isinstance(e, list) else e
    if not e or "entity_id" not in e:
        raise ToolError(f"SwissLipids entity {lipid_id} not found")
    structures, chem = e.get("structures") or {}, e.get("chemical_data") or {}
    classification = e.get("classification") or {}
    synonyms = e.get("synonyms") or []

    # Own reactions, and those of the direct parent classes, once per class
    reactions = reactions_of(e.get("reactions") or {}, None)
    for pid, parent in (classification.get("parents") or {}).items():
        if parent.get("reactions"):
            reactions += reactions_of(
                parent["reactions"], HierarchyNode(id=pid, name=clean(parent.get("entity_name")), level=None)
            )
    unique: dict[tuple[str, str | None], LipidReaction] = {}
    for r in reactions:
        unique.setdefault((r["rhea"], r["inheritedFrom"]["id"] if r["inheritedFrom"] else None), r)
    reactions = list(unique.values())[:MAX_REACTIONS]
    inchikey = none_if(str(structures.get("inchikey") or "").removeprefix("InChIKey="), "none")
    data = LipidData(
        id=e["entity_id"],
        name=clean(e.get("entity_name")),
        abbreviation=next((clean(s["name"]) for s in synonyms if s.get("type") == "abbreviation"), None),
        definition=next((clean(s["name"]) for s in synonyms if s.get("type") == "definition"), None),
        level=level or clean((classification.get("level_name") or "").split(":")[0]) or None,
        formula=none_if(chem.get("formula")),
        mass=float(chem["mass"]) if chem.get("mass") else None,
        charge=int(chem["charge"]) if chem.get("charge") not in (None, "") else None,
        smiles=none_if(structures.get("smiles")),
        inchikey=inchikey,
        depiction=depiction if depiction and depiction.startswith("data:image/") else None,
        synonyms=sorted(
            {clean(s["name"]) for s in synonyms if s.get("type") in ("synonym", "SYNONYM", "name", "NAME")}
            - {clean(e.get("entity_name"))}
        )[:20],
        xrefs=[{"source": x["source"], "id": x["id"]} for x in e.get("xrefs") or [] if x.get("source") != "Rhea"],
        components=[
            {
                "id": cid,
                "name": clean(c[0].get("entity_name")),
                "position": c[0].get("parent_type", "").removeprefix("has_").removesuffix("_parent"),
            }
            for cid, c in (classification.get("components") or {}).items()
            if c
        ],
        lineage=lineage,
        edges=edges,
        children=children,
        childrenTotal=total,
        reactions=reactions,
        locations=locations_of(e.get("summaries") or []),
    )

    # Summary for the model
    def items(values: list[str]) -> str:
        return "; ".join(values) or "none"

    enzymes = {z["accession"]: z for r in reactions for z in r["enzymes"]}
    own = [r for r in reactions if not r["inheritedFrom"]]
    abbreviation = f" ({data['abbreviation']})" if data["abbreviation"] else ""
    lines = [
        f"Shown to the user: SwissLipids {data['id']} {data['name']}{abbreviation}, {data['level']}",
        f"Formula {data['formula']}, mass {data['mass']}, charge {data['charge']}, InChIKey {data['inchikey']}",
        f"SMILES: {data['smiles']}",
        f"Definition: {data['definition']}",
        "Parents in the hierarchy: " + items([f"{n['id']} {n['name']} ({n['level']})" for n in lineage]),
        f"{total} children: " + items([f"{c['id']} {c['name']}" for c in children[:15]]),
        "Chains: " + items([f"{c['position']} {c['id']} {c['name']}" for c in data["components"]]),
        "Cross-references: " + items([f"{x['source']} {x['id']}" for x in data["xrefs"]]),
        f"{len(own)} own Rhea reactions and {len(reactions) - len(own)} inherited from its classes, "
        f"catalyzed by {len(enzymes)} UniProtKB enzymes:",
    ]
    for r in reactions[:25]:
        source = f" (from {r['inheritedFrom']['name']})" if r["inheritedFrom"] else ""
        enzyme_list = ", ".join(f"{z['accession']} {z['name']} ({z['organism']})" for z in r["enzymes"][:6])
        lines.append(f"- RHEA:{r['rhea']} {r['equation']}{source}: {enzyme_list or 'no enzyme'}")
    locations = [f"{x['name']} ({x['id']}, {', '.join(x['taxa'])})" for x in data["locations"]]
    lines.append(f"Found in: {'; '.join(locations) or 'no annotation'}")
    if others:
        lines.append(f"Other lipids matching the search, not shown: {'; '.join(others)}")
    lines.append(
        "The user can browse the hierarchy, reactions, enzymes and locations, and click them to ask about them."
    )
    return text_result("\n".join(lines), data)


apps.add_html_resource(
    "ui://swisslipids/lipid.html",
    widget_html("lipid.html"),
    title="SwissLipids lipid",
    csp=ResourceCsp(resource_domains=[CDN]),
)
