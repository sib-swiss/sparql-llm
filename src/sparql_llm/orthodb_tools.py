"""OrthoDB ortholog group tool showing a MCP Apps widget, calling the OrthoDB API (https://data.orthodb.org) directly.

`show_ortholog_group` shows the ortholog group of a protein at a taxonomic level: its phyletic profile (presence and
copy number per clade and species), its evolutionary descriptors, its functional annotations, and the groups it splits
into at the next levels.
"""

import asyncio
import re
from collections import Counter
from typing import Any

import httpx
from mcp.server.apps import ResourceCsp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from typing_extensions import TypedDict

from sparql_llm.uniprot_tools import CDN, READ_ONLY, apps, get, http_client, text_result, widget_html

ORTHODB_API = "https://data.orthodb.org/current"
OG_ID = re.compile(r"^\s*(\d+at\d+)\s*$")
# Organisms without gene in the group are listed only for levels with fewer species, the counts are always given
MAX_ORGANISMS = 3000
_taxonomy: dict[str, list[dict[str, Any]]] = {}
_taxonomy_lock = asyncio.Lock()


# Data sent to the widget in `structuredContent`, as read by `widgets/orthodb.html`
class Organism(TypedDict):
    id: str
    name: str
    copies: int


class Clade(TypedDict):
    id: str
    name: str
    species: int
    present: int
    """Species with at least one gene in the group"""
    genes: int
    children: list["Clade"]
    organisms: list[Organism]


class LevelGroup(TypedDict):
    id: str
    level: str
    name: str | None
    genes: int
    relation: str
    """parent (broader level), current, or child (the groups it splits into at the next levels)"""


class Annotation(TypedDict):
    id: str
    name: str
    count: int | None


class OrthoGroupData(TypedDict):
    id: str
    name: str
    level: str
    taxId: int
    profile: dict[str, int]
    """gene_count, species_count, present_in, single_copy and multi_copy"""
    rate: float | None
    """Evolutionary rate, the mean divergence of the group relative to the others at the level"""
    architecture: dict[str, float]
    annotations: dict[str, list[Annotation]]
    """InterPro domains, GO terms, EC, KEGG and COG categories, with the number of genes"""
    copies: dict[str, int]
    """Number of species by copy number"""
    clades: Clade | None
    hierarchy: list[LevelGroup]


async def orthodb(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    res = await get(client, f"{ORTHODB_API}/{path}", params)
    if res.status_code != 200:
        raise ToolError(f"OrthoDB API error {res.status_code}: {res.text[:300]}")
    return res.json()


async def taxonomy(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """OrthoDB levels and organisms as a tree, 4 MB fetched once"""
    async with _taxonomy_lock:
        if "tree" not in _taxonomy:
            _taxonomy["tree"] = (await orthodb(client, "tree"))["data"]
    return _taxonomy["tree"]


def find_node(nodes: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for n in nodes:
        if str(n.get("key")) == key:
            return n
        if found := find_node(n.get("children") or [], key):
            return found
    return None


def clade_profile(node: dict[str, Any], counts: dict[str, int], absent: bool) -> Clade:
    """Presence and number of genes of the group in a clade and its sub-clades, organisms are the leaves"""
    children = [clade_profile(c, counts, absent) for c in node.get("children") or [] if "_" not in str(c["key"])]
    leaves = [
        Organism(id=str(c["key"]), name=c["name"].split(", genome")[0], copies=counts.get(str(c["key"]), 0))
        for c in node.get("children") or []
        if "_" in str(c["key"])
    ]
    return Clade(
        id=str(node["key"]),
        name=node["name"],
        species=len(leaves) + sum(c["species"] for c in children),
        present=sum(1 for o in leaves if o["copies"]) + sum(c["present"] for c in children),
        genes=sum(o["copies"] for o in leaves) + sum(c["genes"] for c in children),
        children=sorted(children, key=lambda c: -c["species"]),
        organisms=sorted((o for o in leaves if absent or o["copies"]), key=lambda o: o["name"]),
    )


def all_organisms(clade: Clade) -> list[Organism]:
    return clade["organisms"] + [o for c in clade["children"] for o in all_organisms(c)]


async def find_group(client: httpx.AsyncClient, query: str, level: str | None) -> tuple[str, list[str]]:
    """Ortholog group of a protein at the level asked, the broadest level by default, with the other levels"""
    if m := OG_ID.match(query):
        return m[1], []
    res = await orthodb(client, "search", {"query": query.strip()})
    groups = sorted(res.get("bigdata") or [], key=lambda g: g.get("d2t", 0))
    if not groups:
        raise ToolError(f"No OrthoDB group found for {query!r}, use a UniProt accession (e.g. P04637)")
    chosen = groups[0]
    if level:
        wanted = str(level).strip().lower()
        chosen = next(
            (g for g in groups if wanted in (g["level_name"].lower(), g["id"].split("at")[1])),
            None,
        )
        if not chosen:
            levels = ", ".join(f"{g['level_name']} ({g['id'].split('at')[1]})" for g in groups)
            raise ToolError(f"No OrthoDB group of {query!r} at level {level!r}, levels: {levels}")
    others = [f"{g['id']} {g['level_name']} ({g['gene_count']} genes)" for g in groups if g is not chosen]
    return chosen["id"], others


def hierarchy_of(sankey: dict[str, Any], og_id: str) -> list[LevelGroup]:
    """Groups of the broader levels containing the group, and the groups it splits into at the next levels"""
    nodes = {n["name"]: n for n in sankey.get("nodes", [])}
    parents = {link["target"]: link["source"] for link in sankey.get("links", [])}

    def group(og: str, relation: str) -> LevelGroup:
        n = nodes.get(og, {})
        return LevelGroup(
            id=og,
            level=n.get("cladename", ""),
            name=n.get("description"),
            genes=n.get("cnt_genes", 0),
            relation=relation,
        )

    chain = []
    og = og_id
    while og in parents:
        og = parents[og]
        chain.append(group(og, "parent"))
    children = [group(link["target"], "child") for link in sankey.get("links", []) if link["source"] == og_id]
    return [*reversed(chain), group(og_id, "current"), *sorted(children, key=lambda g: -g["genes"])]


def annotations_of(g: dict[str, Any]) -> dict[str, list[Annotation]]:
    kinds = {
        "InterPro domains": "interpro_domains",
        "GO biological process": "biological_process",
        "GO molecular function": "molecular_function",
        "GO cellular component": "cellular_component",
        "EC": "ec",
        "KEGG pathways": "kegg_pathway",
        "COG category": "functional_category",
    }
    return {
        label: [
            Annotation(id=a.get("id", ""), name=a.get("description") or a.get("name") or "", count=a.get("count"))
            for a in (g.get(key) or [])[:25]
        ]
        for label, key in kinds.items()
        if g.get(key)
    }


@apps.tool(resource_uri="ui://orthodb/orthodb.html", annotations=READ_ONLY)
async def show_ortholog_group(query: str, level: str | None = None) -> CallToolResult:
    """Show the OrthoDB ortholog group of a protein to the user: its phyletic profile (in how many species of each
    clade it is present, and with how many copies), evolutionary descriptors (single or multi copy, evolutionary rate,
    protein length, exons), functional annotations (InterPro, GO, EC, KEGG), and the groups of the broader levels and
    the groups it splits into at the next levels (e.g. paralogs). `query` is a UniProt accession (e.g. P04637) or an
    OrthoDB group ID (e.g. 769296at7742). `level` is the taxonomic level, by name or NCBI taxon ID (e.g. Vertebrata or
    7742, Mammalia, Metazoa, Eukaryota), the broadest level by default"""
    async with http_client() as client:
        og_id, others = await find_group(client, query, level)
        group, counts, sankey, tree = await asyncio.gather(
            orthodb(client, "group", {"id": og_id}),
            orthodb(client, "cluster_clades_cnts", {"cluster_id": og_id}),
            orthodb(client, "single_og_sankey_json", {"start_cluster_id": og_id}),
            taxonomy(client),
        )
    g = group.get("data")
    if not g:
        raise ToolError(f"OrthoDB group {og_id} not found")
    profile = g.get("phyletic_profile") or {}
    node = find_node(tree, str(g["tax_id"]))
    clades = (
        clade_profile(node, counts.get("clade_counts") or {}, profile.get("species_count", 0) <= MAX_ORGANISMS)
        if node
        else None
    )
    copies = Counter(o["copies"] for o in all_organisms(clades) if o["copies"]) if clades else Counter()
    data = OrthoGroupData(
        id=og_id,
        name=g.get("name", ""),
        level=g.get("level_name", ""),
        taxId=g["tax_id"],
        profile={k: int(v) for k, v in profile.items()},
        rate=g.get("evolutionary_rate"),
        architecture=g.get("gene_architecture") or {},
        annotations=annotations_of(g),
        copies={str(k): v for k, v in sorted(copies.items())},
        clades=clades,
        hierarchy=hierarchy_of(sankey, og_id),
    )

    # Summary for the model: presence per clade, down to the clades with fewer species
    def clade_lines(c: Clade, depth: int = 0) -> list[str]:
        line = f"{'  ' * depth}- {c['name']}: present in {c['present']}/{c['species']} species, {c['genes']} genes"
        sub = [
            x
            for child in c["children"]
            if child["species"] >= 5 and (child["present"] or depth == 0)
            for x in clade_lines(child, depth + 1)
        ]
        return [line, *(sub if depth < 3 else [])]

    present, species = profile.get("present_in", 0), profile.get("species_count", 0)
    lines = [
        f"Shown to the user: OrthoDB group {og_id} {data['name']} at the {data['level']} level: {profile.get('gene_count')} "
        f"genes, present in {present}/{species} species ({100 * present / (species or 1):.0f}%), "
        f"single copy in {profile.get('single_copy')}, multi copy in {profile.get('multi_copy')}, "
        f"evolutionary rate {data['rate']}",
        f"Gene architecture: {data['architecture']}",
        "Species by copy number: " + ", ".join(f"{k} copies: {v}" for k, v in data["copies"].items()),
        "Groups at other levels: "
        + "; ".join(
            f"{h['relation']} {h['id']} {h['level']} {h['name']} ({h['genes']} genes)" for h in data["hierarchy"]
        ),
    ]
    if clades:
        lines += ["Phyletic profile:", *clade_lines(clades)]
    for label, items in data["annotations"].items():
        lines.append(f"{label}: " + "; ".join(f"{a['id']} {a['name']} ({a['count']})" for a in items[:8]))
    if others:
        lines.append(f"Groups of the protein at other levels: {'; '.join(others)}")
    lines.append("The user can expand clades down to species, and click groups of other levels to show them.")
    return text_result("\n".join(lines), data)


apps.add_html_resource(
    "ui://orthodb/orthodb.html",
    widget_html("orthodb.html"),
    title="OrthoDB ortholog group",
    csp=ResourceCsp(resource_domains=[CDN]),
)
