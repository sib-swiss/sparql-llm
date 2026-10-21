"""UniProt tools calling the UniProt REST API directly.

- Regular tools returning data to the model: `search_proteins` and `get_protein`
- Tools showing MCP Apps widgets: sequence features, 3D structure with features, search results table,
  variant explorer and annotation matrix. The widget gets the full data in `structuredContent`, the model only gets
  a text summary. Widgets are in `widgets/`, local scripts and stylesheets they reference are inlined when served.

Regular tools are added with `add_uniprot_tools(mcp)`, MCP Apps tools with `MCPServer(extensions=[apps])`.
"""

import asyncio
import heapq
import re
from collections import Counter
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any

import httpx
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent
from typing_extensions import TypedDict

UNIPROT_API = "https://rest.uniprot.org/uniprotkb"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction"
PROTEINS_API = "https://www.ebi.ac.uk/proteins/api"
OMNIPATH_API = "https://omnipathdb.org"
# IntAct evidences of an interaction, in the PSI-MITAB format, queried with MIQL
INTACT_MIQL = "https://www.ebi.ac.uk/Tools/webservices/psicquic/intact/webservices/current/search/query"
WIDGETS = Path(__file__).parent / "widgets"
CDN = "https://cdn.jsdelivr.net"
# UniProt queries not cached yet can take tens of seconds, and the API sometimes answers 503
TIMEOUT = 60
ATTEMPTS = 3

# Feature types shown, grouped in categories like ProtVista tracks
CATEGORIES = {
    "Domains & regions": [
        "Domain",
        "Repeat",
        "Region",
        "Motif",
        "Zinc finger",
        "DNA binding",
        "Coiled coil",
        "Compositional bias",
    ],
    "Sites": ["Active site", "Binding site", "Site"],
    "PTMs": ["Modified residue", "Glycosylation", "Lipidation", "Disulfide bond", "Cross-link"],
    "Processing": ["Signal", "Transit peptide", "Propeptide", "Chain", "Peptide", "Initiator methionine"],
    "Topology": ["Topological domain", "Transmembrane", "Intramembrane"],
    "Secondary structure": ["Helix", "Beta strand", "Turn"],
    "Variants": ["Natural variant", "Mutagenesis"],
}
CATEGORY = {t: c for c, types in CATEGORIES.items() for t in types}
# Variants sent to the explorer, the most documented first: well studied genes have tens of thousands
MAX_VARIANTS = 4000
# GO evidence codes of experimental annotations, IEA ones are electronic
GO_EXPERIMENTAL = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP"}
# Annotation types of the matrix, GO aspects by the prefix of their term
GO_ASPECTS = {"P": "GO biological process", "F": "GO molecular function", "C": "GO cellular component"}
# Keywords of the enzymes whose modification sites are trusted: OmniPath also has text-mined sites of non-enzymes
ENZYME_KEYWORDS = {"KW-0418", "KW-0904"}  # Kinase, Protein phosphatase
UNIPROT_ACCESSION = re.compile(r"^[OPQ]\d[A-Z\d]{3}\d$|^[A-NR-Z]\d([A-Z][A-Z\d]{2}\d){1,2}$")

apps = Apps()


# Data sent to the widgets in `structuredContent`, as read by `widgets/*.html`
class EntryInfo(TypedDict):
    accession: str
    id: str | None
    name: str | None
    gene: str | None
    organism: str | None
    length: int | None
    sequence: str | None


class Feature(TypedDict):
    type: str
    category: str
    start: int
    end: int
    description: str
    change: str | None
    """Amino acid change of variants and mutagenesis, e.g. E17K"""
    refs: list[str]
    """Evidences, e.g. PubMed:123"""


class FeaturesData(EntryInfo):
    features: list[Feature]


class Range(TypedDict):
    start: int
    end: int


class FeaturesViewData(FeaturesData):
    zoom: Range | None
    """Residues zoomed on and highlighted when the viewer opens"""


class AlphaFoldModel(TypedDict):
    entryId: str
    url: str
    plddtUrl: str | None
    meanPlddt: float | None
    sequenceStart: int
    fractions: dict[str, float | None]
    """Fraction of residues per pLDDT confidence level"""


class PdbEntry(TypedDict):
    id: str
    method: str | None
    resolution: float | None
    chains: str | None


class StructureData(FeaturesData):
    alphafold: AlphaFoldModel | None
    pdb: list[PdbEntry]
    source: str
    """`alphafold` or the ID of the PDB entry shown"""
    positions: list[int]


class SearchRow(TypedDict):
    accession: str
    id: str | None
    name: str | None
    gene: str | None
    organism: str | None
    taxId: int | None
    reviewed: bool
    score: int
    length: int | None


class TableData(TypedDict):
    query: str
    total: int
    rows: list[SearchRow]


class Variant(TypedDict):
    start: int
    end: int
    change: str
    """e.g. R175H, or the HGVS protein notation of other changes"""
    aa: str
    """Row in the viewer: the new amino acid, `*` for stops, `d` for other changes"""
    consequence: str
    significance: list[str]
    diseases: list[str]
    evidence: list[str]
    """UniProt (curated), Large scale study, ClinVar, PubMed"""
    clinvar: list[str]
    dbsnp: str | None
    uniprot: str | None
    """UniProt variant ID, e.g. VAR_005851"""
    pubmed: list[str]
    frequency: float | None
    """Highest allele frequency in populations"""


class VariantsData(EntryInfo):
    features: list[Feature]
    """Domains, repeats and motifs, to position the variants"""
    variants: list[Variant]
    total: int
    zoom: Range | None
    """Residues zoomed on and highlighted when the explorer opens"""


class Term(TypedDict):
    id: str
    name: str
    type: str
    """GO aspect, Keyword or Reactome pathway"""


class MatrixProtein(TypedDict):
    accession: str
    gene: str
    name: str | None
    terms: dict[str, int]
    """Term IDs with their evidence: 3 experimental, 2 curated or computational, 1 electronic (GO only)"""


class MatrixData(TypedDict):
    organism: str | None
    proteins: list[MatrixProtein]
    terms: dict[str, Term]
    missing: list[str]
    """Genes without a reviewed entry"""


class Link(TypedDict):
    label: str
    url: str


class NetworkNode(TypedDict):
    accession: str
    gene: str
    name: str | None
    listed: bool
    """In the list given, else a linker added to connect them"""
    via: list[str] | None
    """For linkers: the OmniPath regulations path between 2 listed proteins that made it added"""
    depth: int | None
    """Steps from the source along the best supported path, None when not reachable"""


class Reference(TypedDict):
    pubmed: str
    resources: list[str]
    """OmniPath resources citing it for this relationship"""


class Site(TypedDict):
    label: str
    """e.g. phosphorylation T693"""
    resources: list[str]


class Regulation(TypedDict):
    source: str
    target: str
    effect: str
    """activation, inhibition, mixed (both reported) or unknown"""
    majority: str | None
    """Effect reported by most resources, when mixed"""
    evidence: int
    """OmniPath curation effort: number of unique resource and reference pairs"""
    resources: list[str]
    """Resources combined by OmniPath for this relationship"""
    references: list[Reference]
    sites: list[Site]
    """Modifications of the target by the source, from OmniPath enzyme-substrate relationships"""
    links: list[Link]
    """OmniPath records of the relationship and its sites"""


class PhysicalInteraction(TypedDict):
    a: str
    b: str
    experiments: int
    """Number of IntAct experiments, as summarized in UniProtKB"""
    links: list[Link]


class Pathway(TypedDict):
    id: str
    name: str
    members: list[str]
    """Proteins annotated with the pathway in their UniProtKB cross-references"""
    links: list[Link]


class DataSource(TypedDict):
    name: str
    provides: str
    url: str
    """Query of the data used, or home page"""


class Feedback(TypedDict):
    source: str
    target: str
    """Edge going back upstream, from `source` to `target`"""
    loop: list[str]
    """Shortest directed path from `target` back to `source`, closed by the edge"""


class NetworkData(TypedDict):
    organism: str | None
    source: str
    target: str | None
    nodes: list[NetworkNode]
    regulations: list[Regulation]
    interactions: list[PhysicalInteraction]
    pathways: list[Pathway]
    paths: list[list[str]]
    """Best supported directed paths from `source` to `target`"""
    feedback: list[Feedback]
    missing: list[str]
    sources: list[DataSource]


def text_result(text: str, data: Mapping[str, Any]) -> CallToolResult:
    """Summary for the model, full data for the widget"""
    return CallToolResult(content=[TextContent(type="text", text=text)], structured_content=dict(data))


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT)


async def get(client: httpx.AsyncClient, url: str, params: Any = None) -> httpx.Response:
    """GET retried on timeouts and server errors, which are transient on the UniProt and AlphaFold APIs"""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            res = await client.get(url, params=params)
            if res.status_code < 500 or attempt == ATTEMPTS:
                return res
        except httpx.TransportError:
            if attempt == ATTEMPTS:
                raise ToolError(f"{url} did not answer after {ATTEMPTS} attempts, try again later") from None
        await asyncio.sleep(attempt)
    raise AssertionError("unreachable")


async def fetch_entry(client: httpx.AsyncClient, accession: str) -> dict[str, Any]:
    res = await get(client, f"{UNIPROT_API}/{accession.strip()}.json")
    if res.status_code in (400, 404):
        raise ToolError(f"UniProtKB entry {accession!r} not found")
    res.raise_for_status()
    return res.json()


def protein_name(e: dict[str, Any]) -> str | None:
    desc = e.get("proteinDescription", {})
    name: dict[str, Any] = desc.get("recommendedName") or next(iter(desc.get("submissionNames") or []), {})
    return name.get("fullName", {}).get("value")


def entry_info(e: dict[str, Any]) -> EntryInfo:
    genes = [g["geneName"]["value"] for g in e.get("genes", []) if "geneName" in g]
    return {
        "accession": e["primaryAccession"],
        "id": e.get("uniProtkbId"),
        "name": protein_name(e),
        "gene": next(iter(genes), None),
        "organism": e.get("organism", {}).get("scientificName"),
        "length": e.get("sequence", {}).get("length"),
        "sequence": e.get("sequence", {}).get("value"),
    }


def features_of(e: dict[str, Any]) -> list[Feature]:
    """Features with known positions, for the types shown in tracks"""
    features: list[Feature] = []
    for f in e.get("features", []):
        start, end = f["location"]["start"].get("value"), f["location"]["end"].get("value")
        if f["type"] not in CATEGORY or start is None or end is None:
            continue
        alt = f.get("alternativeSequence") or {}
        change = None
        if alt.get("originalSequence"):
            change = f"{alt['originalSequence']}{start}{'/'.join(alt.get('alternativeSequences') or []) or 'del'}"
        refs = [f"{ev['source']}:{ev['id']}" for ev in f.get("evidences", []) if ev.get("source") and ev.get("id")]
        features.append(
            {
                "type": f["type"],
                "category": CATEGORY[f["type"]],
                "start": start,
                "end": end,
                "description": f.get("description") or (f.get("ligand") or {}).get("name") or "",
                "change": change,
                "refs": refs[:5],
            }
        )
    return features


def feature_label(f: Feature, max_len: int = 60) -> str:
    pos = str(f["start"]) if f["start"] == f["end"] else f"{f['start']}-{f['end']}"
    desc = f["description"].split(";")[0]
    desc = desc if len(desc) <= max_len else desc[: max_len - 3] + "..."
    return " ".join(x for x in [f["change"] or pos, desc] if x)


def features_text(features: list[Feature], per_type: int = 25) -> str:
    """Features listed by type, a few per type"""
    by_type: dict[str, list[Feature]] = {}
    for f in features:
        by_type.setdefault(f["type"], []).append(f)
    lines = []
    for t, fs in by_type.items():
        more = f"; +{len(fs) - per_type} more" if len(fs) > per_type else ""
        lines.append(f"- {t} ({len(fs)}): " + "; ".join(feature_label(f) for f in fs[:per_type]) + more)
    return "\n".join(lines)


def entry_title(info: EntryInfo) -> str:
    return f"{info['accession']} ({info['id']}, {info['name']}, {info['organism']}, {info['length']} aa)"


# Regular tools, typed results give them an output schema
class ProteinSummary(TypedDict):
    accession: str
    name: str | None
    genes: list[str]
    organism: str | None
    length: int | None


class Protein(TypedDict):
    accession: str
    name: str | None
    organism: str | None
    function: list[str]
    sequence: str | None


async def search_proteins(query: str, size: int = 5) -> list[ProteinSummary]:
    """Search UniProtKB entries, returns accession, name, genes, organism. Query syntax: `gene_exact:INS`,
    `protein_name:kinase`, `organism_id:9606` (one species), `taxonomy_name:mammalia` (a clade with its
    descendants, by name), `reviewed:true`, `cc_disease:*`, combined with AND, OR, NOT"""
    params = {
        "query": query,
        "size": size,
        "fields": "accession,protein_name,gene_names,organism_name,length",
    }
    async with http_client() as client:
        res = await get(client, f"{UNIPROT_API}/search", params)
    # Invalid queries are explained to the model, which can fix them
    if res.status_code == 400:
        raise ToolError(f"Invalid query: {', '.join(res.json().get('messages', []))}")
    res.raise_for_status()
    return [
        ProteinSummary(
            accession=e["primaryAccession"],
            name=protein_name(e),
            genes=[g["geneName"]["value"] for g in e.get("genes", []) if "geneName" in g],
            organism=e.get("organism", {}).get("scientificName"),
            length=e.get("sequence", {}).get("length"),
        )
        for e in res.json()["results"]
    ]


async def get_protein(accession: str) -> Protein:
    """Get a UniProtKB entry by accession (e.g. P01308): name, organism, function and sequence"""
    async with http_client() as client:
        e = await fetch_entry(client, accession)
    return Protein(
        accession=e["primaryAccession"],
        name=protein_name(e),
        organism=e.get("organism", {}).get("scientificName"),
        function=[
            t["value"] for c in e.get("comments", []) if c["commentType"] == "FUNCTION" for t in c.get("texts", [])
        ],
        sequence=e.get("sequence", {}).get("value"),
    )


def add_uniprot_tools(mcp: MCPServer) -> None:
    """Add the regular UniProt tools to a MCP server, the MCP Apps ones are added with `extensions=[apps]`"""
    mcp.add_tool(search_proteins)
    mcp.add_tool(get_protein)


# MCP Apps tools, showing their result in a widget
def residue_range(start: int | None, end: int | None, length: int | None) -> Range | None:
    """Range of residues from optional bounds, a single residue when only one is given, within the sequence"""
    if start is None and end is None:
        return None
    first, last = sorted((start or end or 1, end or start or 1))
    if length and first > length:
        raise ToolError(f"Residue {first} is after the end of the sequence, which has {length} residues")
    return Range(start=max(1, first), end=min(last, length or last))


def range_label(r: Range) -> str:
    return f"residue {r['start']}" if r["start"] == r["end"] else f"residues {r['start']}-{r['end']}"


def in_range(v: Variant | Feature, r: Range | None) -> bool:
    return r is not None and v["start"] <= r["end"] and v["end"] >= r["start"]


@apps.tool(resource_uri="ui://uniprot/features.html")
async def show_protein_features(accession: str, start: int | None = None, end: int | None = None) -> CallToolResult:
    """Show the sequence features of a UniProtKB entry (e.g. P31749) to the user in an interactive track viewer,
    zoomable along the sequence: domains, sites, PTMs, signal peptides, topology, secondary structure and variants.
    To focus on a region, give its UniProt residue positions in `start` and `end` (e.g. 102 and 234 for a domain, or
    only `start` for a single residue such as a mutation): the viewer opens zoomed on it, with the region highlighted"""
    async with http_client() as client:
        e = await fetch_entry(client, accession)
    info, features = entry_info(e), features_of(e)
    zoom = residue_range(start, end, info["length"])
    text = f"Shown to the user: {len(features)} features of {entry_title(info)}"
    if zoom:
        # Features overlapping the region first, the chain spans the whole sequence
        region = range_label(zoom)
        inside = [f for f in features if in_range(f, zoom) and f["type"] != "Chain"]
        text += (
            f"\nZoomed on {region}, highlighted, with {len(inside)} features overlapping "
            f"them:\n{features_text(inside) or '- none'}\nAll features:"
        )
    text += f"\n{features_text(features)}"
    return text_result(text, FeaturesViewData(**info, features=features, zoom=zoom))


async def fetch_alphafold(client: httpx.AsyncClient, accession: str) -> AlphaFoldModel | None:
    """AlphaFold DB model of the full sequence, if any"""
    res = await get(client, f"{ALPHAFOLD_API}/{accession}")
    if res.status_code != 200:
        return None
    model = next((m for m in res.json() if m.get("uniprotAccession") == accession), None)
    if not model:
        return None
    return {
        "entryId": model["modelEntityId"],
        "url": model["bcifUrl"],
        "plddtUrl": model.get("plddtDocUrl"),
        "meanPlddt": model.get("globalMetricValue"),
        "sequenceStart": model.get("sequenceStart", 1),
        "fractions": {
            "very high": model.get("fractionPlddtVeryHigh"),
            "confident": model.get("fractionPlddtConfident"),
            "low": model.get("fractionPlddtLow"),
            "very low": model.get("fractionPlddtVeryLow"),
        },
    }


def pdb_entries(e: dict[str, Any]) -> list[PdbEntry]:
    """PDB cross-references of the entry, best resolution first"""
    entries: list[PdbEntry] = []
    for x in e.get("uniProtKBCrossReferences", []):
        if x["database"] != "PDB":
            continue
        props = {p["key"]: p["value"] for p in x.get("properties", [])}
        resolution = re.match(r"[\d.]+", props.get("Resolution", ""))
        entries.append(
            {
                "id": x["id"].lower(),
                "method": props.get("Method"),
                "resolution": float(resolution.group()) if resolution else None,
                "chains": props.get("Chains"),
            }
        )
    return sorted(entries, key=lambda p: p["resolution"] or 99)


@apps.tool(resource_uri="ui://uniprot/structure.html")
async def show_protein_structure(
    accession: str, pdb_id: str | None = None, positions: list[int] | None = None
) -> CallToolResult:
    """Show the 3D structure of a UniProtKB entry to the user in Mol*: the AlphaFold model colored by pLDDT
    confidence, or a PDB entry with `pdb_id`. Its features and variants are listed next to it, clicking one highlights
    its residues. `positions` are UniProt residue numbers highlighted first, e.g. the position of a mutation"""
    async with http_client() as client:
        e, alphafold = await asyncio.gather(fetch_entry(client, accession), fetch_alphafold(client, accession))
        # Confidence of the highlighted residues
        plddt: dict[int, float] = {}
        if positions and alphafold and alphafold["plddtUrl"]:
            res = await get(client, alphafold["plddtUrl"])
            if res.status_code == 200:
                doc = res.json()
                plddt = dict(zip(doc["residueNumber"], doc["confidenceScore"], strict=False))
    info, features, pdb = entry_info(e), features_of(e), pdb_entries(e)
    source = pdb_id.lower() if pdb_id else "alphafold" if alphafold else pdb[0]["id"] if pdb else None
    if not source:
        raise ToolError(f"No AlphaFold model or PDB entry for {accession}")
    positions = positions or []
    # PDB entries the user can switch to in the widget
    data = StructureData(
        **info, features=features, alphafold=alphafold, pdb=pdb[:100], source=source, positions=positions
    )

    # Summary: structure shown, confidence, features at the highlighted positions, other structures
    lines = [f"Shown to the user: 3D structure of {entry_title(info)}"]
    if source == "alphafold" and alphafold:
        fractions = ", ".join(f"{round(v * 100)}% {k}" for k, v in alphafold["fractions"].items() if v is not None)
        lines.append(f"AlphaFold model {alphafold['entryId']}, mean pLDDT {alphafold['meanPlddt']} ({fractions})")
    else:
        lines.append(f"PDB entry {source.upper()}, residues numbered as in UniProt")
    for p in positions:
        at = [
            feature_label(f) + f" [{f['type']}]"
            for f in features
            if f["start"] <= p <= f["end"] and f["type"] != "Chain"
        ]
        conf = f", pLDDT {plddt[p]}" if p in plddt else ""
        lines.append(f"Residue {p} highlighted{conf}, in: {'; '.join(at) or 'no annotated feature'}")
    if pdb:
        best = ", ".join(
            f"{p['id'].upper()} ({p['method']}, {p['resolution'] or '-'} A, {p['chains']})" for p in pdb[:15]
        )
        lines.append(f"PDB entries ({len(pdb)}): {best}")
    lines.append("The user can click the features listed in the widget to highlight their residues.")
    return text_result("\n".join(lines), data)


def search_row(e: dict[str, Any]) -> SearchRow:
    return {
        "accession": e["primaryAccession"],
        "id": e.get("uniProtkbId"),
        "name": protein_name(e),
        "gene": next((g["geneName"]["value"] for g in e.get("genes", []) if "geneName" in g), None),
        "organism": e.get("organism", {}).get("scientificName"),
        "taxId": e.get("organism", {}).get("taxonId"),
        "reviewed": "Swiss-Prot" in e.get("entryType", ""),
        "score": int(e.get("annotationScore") or 0),
        "length": e.get("sequence", {}).get("length"),
    }


def counts(values: list[Any], top: int = 8) -> str:
    return ", ".join(f"{k}: {n}" for k, n in Counter(values).most_common(top))


@apps.tool(resource_uri="ui://uniprot/table.html")
async def search_proteins_table(query: str, max_rows: int = 1000) -> CallToolResult:
    """Search UniProtKB and show all results to the user in a sortable table, with facets for reviewed status,
    organism and annotation score. Only a summary is returned: the user can select rows in the table and send them back
    to you. Query syntax: `gene_exact:INS`, `protein_name:kinase`, `organism_id:9606` (one species),
    `taxonomy_name:mammalia` (a clade with its descendants, by name), `reviewed:true`, `cc_disease:*`, combined with
    AND, OR, NOT"""
    params = {
        "query": query,
        "size": min(500, max_rows),
        "fields": "accession,id,protein_name,gene_primary,organism_name,reviewed,annotation_score,length",
    }
    rows: list[SearchRow] = []
    async with http_client() as client:
        res = await get(client, f"{UNIPROT_API}/search", params)
        if res.status_code == 400:
            raise ToolError(f"Invalid query: {', '.join(res.json().get('messages', []))}")
        res.raise_for_status()
        total = int(res.headers.get("x-total-results", 0))
        rows += [search_row(e) for e in res.json()["results"]]
        # Next pages, with the cursor in the `Link` header
        while len(rows) < max_rows and "next" in res.links:
            res = await get(client, res.links["next"]["url"])
            res.raise_for_status()
            rows += [search_row(e) for e in res.json()["results"]]
    rows = rows[:max_rows]

    reviewed = sum(r["reviewed"] for r in rows)
    first = "; ".join(f"{r['accession']} {r['gene'] or r['id']} {r['name']}" for r in rows[:10])
    text = (
        f"Shown to the user in a table: {len(rows)} of {total} UniProtKB entries matching `{query}`.\n"
        f"Reviewed (Swiss-Prot): {reviewed}, unreviewed (TrEMBL): {len(rows) - reviewed}\n"
        f"Organisms: {counts([r['organism'] for r in rows])}\n"
        f"Annotation scores: {counts([r['score'] for r in rows], 5)}\n"
        f"First rows: {first}\n"
        "The user can filter, sort and select rows in the table, the selection is sent to you."
    )
    return text_result(text, TableData(query=query, total=total, rows=rows))


async def fetch_variants(client: httpx.AsyncClient, accession: str) -> list[dict[str, Any]]:
    """Variants of the EBI Proteins API: UniProt, ClinVar, dbSNP, gnomAD, COSMIC..."""
    res = await get(client, f"{PROTEINS_API}/variation/{accession}")
    if res.status_code == 404:
        return []
    res.raise_for_status()
    return res.json().get("features", [])


def variant_of(v: dict[str, Any]) -> Variant:
    start = int(v["begin"])
    wild, new = v.get("wildType"), v.get("mutatedType") or v.get("alternativeSequence")
    consequence = v.get("consequenceType") or "-"
    if wild and new and len(wild) == len(new) == 1:
        change = f"{wild}{start}{new}"
    else:
        protein_locs = (loc["loc"] for loc in v.get("locations", []) if loc["loc"].startswith("p."))
        change = next(protein_locs, f"{wild or ''}{start}")
    xrefs = v.get("xrefs", [])
    evidences = v.get("evidences", []) + [ev for a in v.get("association", []) for ev in a.get("evidences", [])]
    pubmed = list(dict.fromkeys(ev["source"]["id"] for ev in evidences if ev["source"]["name"] == "pubmed"))
    clinvar = list(dict.fromkeys(x["id"] for x in xrefs if x["name"] == "ClinVar"))
    source = v.get("sourceType")
    evidence = [
        name
        for name, ok in [
            ("UniProt", source in ("uniprot", "mixed")),
            ("Large scale study", source in ("large_scale_study", "mixed")),
            ("ClinVar", bool(clinvar)),
            ("PubMed", bool(pubmed)),
        ]
        if ok
    ]
    frequencies = [f["frequency"] for f in v.get("populationFrequencies", []) if f.get("frequency")]
    return Variant(
        start=start,
        end=int(v.get("end") or start),
        change=change,
        aa=new if consequence == "missense" and new and len(new) == 1 else "*" if consequence == "stop gained" else "d",
        consequence="other" if consequence == "-" else consequence,
        significance=list(dict.fromkeys(c["type"] for c in v.get("clinicalSignificances", []))),
        diseases=list(dict.fromkeys(a["name"] for a in v.get("association", [])))[:5],
        evidence=evidence,
        clinvar=clinvar[:5],
        dbsnp=next((x["id"] for x in xrefs if x["name"] == "dbSNP"), None),
        uniprot=v.get("ftId"),
        pubmed=pubmed[:5],
        frequency=max(frequencies, default=None),
    )


def variant_rank(v: Variant) -> tuple[bool, ...]:
    """Most documented first: curated, pathogenic, with a clinical significance, a disease, a dbSNP ID"""
    pathogenic = any("athogenic" in s or s == "Disease" for s in v["significance"])
    return ("UniProt" in v["evidence"], pathogenic, bool(v["significance"]), bool(v["diseases"]), bool(v["dbsnp"]))


@apps.tool(resource_uri="ui://uniprot/variants.html")
async def show_protein_variants(accession: str, start: int | None = None, end: int | None = None) -> CallToolResult:
    """Show the disease and natural variants of a UniProtKB entry (e.g. P04637) to the user in an interactive
    explorer: variants positioned on the sequence next to domains, filterable by consequence, clinical significance,
    evidence and disease, with links to ClinVar, dbSNP and publications.
    To focus on a region, give its UniProt residue positions in `start` and `end` (e.g. 102 and 234 for a domain, or
    only `start` for a single residue): the explorer opens zoomed on it, with the region highlighted"""
    async with http_client() as client:
        e, raw = await asyncio.gather(fetch_entry(client, accession), fetch_variants(client, accession))
    info = entry_info(e)
    zoom = residue_range(start, end, info["length"])
    # Variants of the region kept first when there are too many to send
    variants = sorted((variant_of(v) for v in raw), key=lambda v: (in_range(v, zoom), *variant_rank(v)), reverse=True)[
        :MAX_VARIANTS
    ]
    variants.sort(key=lambda v: v["start"])
    domains = [f for f in features_of(e) if f["type"] in ("Domain", "Repeat", "Zinc finger", "DNA binding", "Motif")]

    # Summary: counts, diseases, hotspots and curated pathogenic variants
    pathogenic = [v for v in variants if any("athogenic" in s or s == "Disease" for s in v["significance"])]
    curated = [v for v in pathogenic if "UniProt" in v["evidence"]]
    hotspots = Counter(v["start"] for v in pathogenic).most_common(8)
    shown = f"{len(variants)} most documented of {len(raw)}" if len(raw) > len(variants) else str(len(variants))
    text = "\n".join(
        [
            f"Shown to the user: {shown} variants of {entry_title(info)}",
            f"Consequences: {counts([v['consequence'] for v in variants])}",
            f"Clinical significance: {counts([s for v in variants for s in v['significance']])}",
            f"Diseases: {counts([d for v in variants for d in v['diseases']], 10)}",
            f"Positions with most pathogenic variants: {', '.join(f'{p} ({n})' for p, n in hotspots) or 'none'}",
            "Pathogenic variants curated in UniProt: "
            + ("; ".join(f"{v['change']} ({', '.join(v['diseases'][:2]) or '-'})" for v in curated[:30]) or "none"),
            "The user can filter the variants and click them for details and links to ClinVar and dbSNP.",
        ]
    )
    if zoom:
        # Variants of the region, the most documented first
        inside = sorted((v for v in variants if in_range(v, zoom)), key=variant_rank, reverse=True)
        listed = "; ".join(
            f"{v['change']} ({', '.join(v['significance']) or 'no significance'}"
            + (f", {', '.join(v['diseases'][:2])}" if v["diseases"] else "")
            + ")"
            for v in inside[:30]
        )
        text += (
            f"\nZoomed on {range_label(zoom)}, highlighted, with {len(inside)} variants in it"
            + (f", the most documented: {listed}" if listed else "")
            + f"\nClinical significance in it: {counts([s for v in inside for s in v['significance']]) or 'none'}"
        )
    return text_result(text, VariantsData(**info, features=domains, variants=variants, total=len(raw), zoom=zoom))


def go_level(evidence_type: str) -> int:
    code = evidence_type.split(":")[0]
    return 3 if code in GO_EXPERIMENTAL else 1 if code == "IEA" else 2


def gene_name(e: dict[str, Any]) -> str:
    return next((g["geneName"]["value"] for g in e.get("genes", []) if "geneName" in g), e["primaryAccession"])


async def fetch_genes(
    client: httpx.AsyncClient, genes: list[str], organism_id: int, fields: str
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Reviewed UniProtKB entries of a gene list with the given extra fields, one per gene: the one with it as primary
    name, else as synonym. Returns the (gene, entry) pairs found, without duplicate entries, and the genes not found"""
    genes = list(dict.fromkeys(g.strip() for g in genes if g.strip()))[:100]
    if not genes:
        raise ToolError("No gene given")
    params = {
        "query": f"({' OR '.join(f'gene_exact:{g}' for g in genes)}) AND organism_id:{organism_id} AND reviewed:true",
        "size": 500,
        "fields": f"accession,gene_names,protein_name,organism_name,{fields}",
    }
    res = await get(client, f"{UNIPROT_API}/search", params)
    if res.status_code == 400:
        raise ToolError(f"Invalid gene list: {', '.join(res.json().get('messages', []))}")
    res.raise_for_status()
    results = res.json()["results"]
    names = [{g["geneName"]["value"].upper() for g in e.get("genes", []) if "geneName" in g} for e in results]
    synonyms = [{s["value"].upper() for g in e.get("genes", []) for s in g.get("synonyms", [])} for e in results]
    found: list[tuple[str, dict[str, Any]]] = []
    missing = []
    for gene in genes:
        entry = next((e for e, n in zip(results, names, strict=True) if gene.upper() in n), None) or next(
            (e for e, n in zip(results, synonyms, strict=True) if gene.upper() in n), None
        )
        if not entry:
            missing.append(gene)
        elif all(e["primaryAccession"] != entry["primaryAccession"] for _, e in found):
            found.append((gene, entry))
    if not found:
        raise ToolError(f"No reviewed UniProtKB entry for {', '.join(genes)} in organism {organism_id}")
    return found, missing


def matrix_protein(e: dict[str, Any], terms: dict[str, Term]) -> MatrixProtein:
    """GO terms, keywords (except technical ones) and Reactome pathways of an entry, added to `terms`"""
    annotations: dict[str, int] = {}
    for x in e.get("uniProtKBCrossReferences", []):
        props = {p["key"]: p["value"] for p in x.get("properties", [])}
        if x["database"] == "GO" and "GoTerm" in props:
            aspect, name = props["GoTerm"].split(":", 1)
            terms[x["id"]] = Term(id=x["id"], name=name, type=GO_ASPECTS[aspect])
            annotations[x["id"]] = go_level(props.get("GoEvidenceType", ""))
        elif x["database"] == "Reactome":
            terms[x["id"]] = Term(id=x["id"], name=props.get("PathwayName", x["id"]), type="Reactome pathway")
            annotations[x["id"]] = 3
    for k in e.get("keywords", []):
        if k["category"] not in ("Technical term", "Coding sequence diversity"):
            terms[k["id"]] = Term(id=k["id"], name=k["name"], type="Keyword")
            annotations[k["id"]] = 3
    return MatrixProtein(accession=e["primaryAccession"], gene=gene_name(e), name=protein_name(e), terms=annotations)


@apps.tool(resource_uri="ui://uniprot/matrix.html")
async def show_annotation_matrix(genes: list[str], organism_id: int = 9606) -> CallToolResult:
    """Show a heatmap of the reviewed UniProtKB entries of a gene list (e.g. ["TP53", "MDM2", "CDKN1A"]) by their
    GO terms, keywords or Reactome pathways to the user, for a quick functional overview of the list.
    `organism_id` is the NCBI taxonomy ID, human by default"""
    async with http_client() as client:
        entries, missing = await fetch_genes(client, genes, organism_id, "go,keyword,xref_reactome")
    terms: dict[str, Term] = {}
    proteins = [matrix_protein(e, terms) for _, e in entries]
    organism = next((e.get("organism", {}).get("scientificName") for _, e in entries), None)

    # Summary: terms shared by most proteins, per annotation type
    lines = [f"Shown to the user: annotation matrix of {len(proteins)} {organism} proteins"]
    if missing:
        lines.append(f"No reviewed entry for: {', '.join(missing)}")
    for kind in [*GO_ASPECTS.values(), "Keyword", "Reactome pathway"]:
        shared = Counter(t for p in proteins for t in p["terms"] if terms[t]["type"] == kind).most_common(8)
        top = "; ".join(
            f"{terms[t]['name']} ({n}: {', '.join(p['gene'] for p in proteins if t in p['terms'])})"
            for t, n in shared
            if n > 1
        )
        lines.append(f"Most shared, {kind}: {top or 'none'}")
    lines.append("The user can switch annotation types and click terms or proteins to ask about them.")
    return text_result("\n".join(lines), MatrixData(organism=organism, proteins=proteins, terms=terms, missing=missing))


NETWORK_FIELDS = "cc_interaction,xref_reactome,keyword"


async def fetch_omnipath(
    client: httpx.AsyncClient, endpoint: str, params: dict[str, Any], organism_id: int
) -> list[dict[str, Any]]:
    """OmniPath records between UniProt accessions, complexes excluded"""
    params = {**params, "organisms": organism_id, "genesymbols": "yes", "format": "json"}
    res = await get(client, f"{OMNIPATH_API}/{endpoint}", params)
    res.raise_for_status()
    keys = ("source", "target") if endpoint == "interactions" else ("enzyme", "substrate")
    return [r for r in res.json() if all(UNIPROT_ACCESSION.match(r[k]) for k in keys)]


def omnipath_url(endpoint: str, sources: list[str], targets: list[str], organism_id: int) -> str:
    """Human readable (TSV) OmniPath query of the records between sources and targets, with their provenance"""
    keys = (
        ("sources", "targets", "source_target")
        if endpoint == "interactions"
        else ("enzymes", "substrates", "enzyme_substrate")
    )
    params = {
        keys[0]: ",".join(sources),
        keys[1]: ",".join(targets),
        keys[2]: "AND",
        "organisms": organism_id,
        "genesymbols": "yes",
        "fields": "sources,references,curation_effort",
    }
    return str(httpx.URL(f"{OMNIPATH_API}/{endpoint}", params=params))


def by_resource(refs: str) -> dict[str, list[str]]:
    """OmniPath references `Resource:PMID;...` grouped by PubMed ID, derived resources `Resource_Origin` merged"""
    grouped: dict[str, list[str]] = {}
    for ref in refs.split(";"):
        resource, _, pmid = ref.partition(":")
        # PubMed IDs only, as reported by the resources
        if pmid.isdigit():
            grouped.setdefault(pmid, [])
            if resource.split("_")[0] not in grouped[pmid]:
                grouped[pmid].append(resource.split("_")[0])
    return grouped


def regulation_of(r: dict[str, Any], organism_id: int) -> Regulation:
    """Directed OmniPath interaction, with its effect and provenance"""
    stim, inh = r["is_stimulation"], r["is_inhibition"]
    effect = "mixed" if stim and inh else "activation" if stim else "inhibition" if inh else "unknown"
    majority = None
    if effect == "mixed" and r["consensus_stimulation"] != r["consensus_inhibition"]:
        majority = "activation" if r["consensus_stimulation"] else "inhibition"
    # Most cited references first
    refs = sorted(by_resource(r.get("references") or "").items(), key=lambda x: -len(x[1]))
    return Regulation(
        source=r["source"],
        target=r["target"],
        effect=effect,
        majority=majority,
        evidence=int(r.get("curation_effort") or 0),
        resources=list(dict.fromkeys(s.split("_")[0] for s in r.get("sources", []))),
        references=[Reference(pubmed=p, resources=res) for p, res in refs[:10]],
        sites=[],
        links=[
            Link(label="OmniPath records", url=omnipath_url("interactions", [r["source"]], [r["target"]], organism_id))
        ],
    )


def pick_linkers(records: list[dict[str, Any]], listed: set[str], max_linkers: int) -> dict[str, list[str]]:
    """Proteins not listed with a directed edge from a listed protein and one to another, best supported first,
    with their best supported path between the 2 listed proteins"""
    into: dict[str, dict[str, int]] = {}
    out: dict[str, dict[str, int]] = {}
    for r in records:
        if r["source"] in listed and r["target"] not in listed:
            into.setdefault(r["target"], {})[r["source"]] = r["curation_effort"]
        elif r["target"] in listed and r["source"] not in listed:
            out.setdefault(r["source"], {})[r["target"]] = r["curation_effort"]
    best = {
        x: max(((min(ea, eb), [a, x, b]) for a, ea in into[x].items() for b, eb in out[x].items() if a != b))
        for x in into.keys() & out.keys()
        if any(a != b for a in into[x] for b in out[x])
    }
    return {x: best[x][1] for x in sorted(best, key=lambda x: best[x][0], reverse=True)[:max_linkers]}


Graph = dict[str, dict[str, int]]
"""Evidence of the regulations by source and target"""


def best_paths(graph: Graph, start: str, end: str, limit: int = 5, max_len: int = 8) -> list[list[str]]:
    """Simple directed paths from `start` to `end`, the best supported first: highest minimum evidence along the path,
    then fewest steps. Depth-first search pruning paths that cannot beat the ones found, with a budget of steps"""
    found: list[tuple[int, int, list[str]]] = []
    budget = 50000

    def walk(path: list[str], width: int) -> None:
        nonlocal budget
        budget -= 1
        # Pruned when it cannot rank in the `limit` best: weaker, or as weak and not shorter
        if budget < 0 or len(path) > max_len + 1 or (len(found) >= limit and (-width, len(path)) >= found[-1][:2]):
            return
        if path[-1] == end:
            found.append((-width, len(path), path))
            found.sort(key=lambda f: f[:2])
            del found[limit:]
            return
        for v, evidence in sorted(graph.get(path[-1], {}).items(), key=lambda x: -x[1]):
            if v not in path:
                walk([*path, v], min(width, evidence))

    walk([start], 10**9)
    return [p for _, _, p in found]


def signal_depth(graph: Graph, start: str) -> dict[str, int]:
    """Steps from `start` to each node reachable from it, along its best supported path (as `best_paths`)"""
    best = {start: (10**9, 0)}
    heap = [(-(10**9), 0, start)]
    while heap:
        width, steps, u = heapq.heappop(heap)
        if (-width, steps) != best[u]:
            continue
        for v, evidence in graph.get(u, {}).items():
            cand = (min(-width, evidence), steps + 1)
            if v not in best or (-cand[0], cand[1]) < (-best[v][0], best[v][1]):
                best[v] = cand
                heapq.heappush(heap, (-cand[0], cand[1], v))
    return {n: steps for n, (_, steps) in best.items()}


def feedback_edges(regulations: list[Regulation], graph: Graph, depth: dict[str, int]) -> list[Feedback]:
    """Edges going back upstream: to a node closer to the source along the best supported paths (`depth` from
    `signal_depth`), closing a loop. Inhibitions and best supported first"""
    loops: list[tuple[Regulation, list[str]]] = []
    for r in regulations:
        u, v = r["source"], r["target"]
        if u == v or depth.get(v, 99) >= depth.get(u, 99):
            continue
        back = best_paths(graph, v, u, limit=1)
        if back:
            loops.append((r, back[0]))
    rank = {"inhibition": 0, "mixed": 1, "unknown": 2, "activation": 3}
    loops.sort(key=lambda x: (rank[x[0]["effect"]], -x[0]["evidence"]))
    return [Feedback(source=r["source"], target=r["target"], loop=loop) for r, loop in loops[:30]]


@apps.tool(resource_uri="ui://uniprot/network.html")
async def show_protein_network(
    genes: list[str],
    source: str | None = None,
    target: str | None = None,
    organism_id: int = 9606,
    max_linkers: int = 5,
) -> CallToolResult:
    """Show an interactive graph connecting a list of proteins to the user, distinguishing 3 kinds of sourced
    relationships: directed regulations (activation, inhibition) from OmniPath with their resources, references and
    modification sites, physical interactions from IntAct (via UniProtKB), and Reactome pathway membership.
    Shows the best supported directed paths from `source` to `target`, and the feedback loops going back upstream.

    Give official gene symbols, including the expected intermediates, e.g. to connect EGFR to ERK:
    ["EGFR", "GRB2", "SOS1", "HRAS", "RAF1", "MAP2K1", "MAPK1", "MAPK3"] with source "EGFR" and target "MAPK1".
    `source` defaults to the first gene. Up to `max_linkers` proteins not listed are added when they connect 2 listed
    proteins. `organism_id` is the NCBI taxonomy ID: 9606 (human, default), 10090 (mouse) or 10116 (rat)"""
    genes = [g for g in [source, *genes, target] if g]
    async with http_client() as client:
        entries, missing = await fetch_genes(client, genes, organism_id, NETWORK_FIELDS)
        by_gene = {g.upper(): e["primaryAccession"] for g, e in entries}
        listed = [e for _, e in entries]
        accs = [e["primaryAccession"] for e in listed]

        # Directed interactions between the listed proteins, or touching them to find linkers
        params = {"sources": ",".join(accs), "targets": ",".join(accs), "fields": "sources,references,curation_effort"}
        if not max_linkers:
            params["source_target"] = "AND"
        records = [r for r in await fetch_omnipath(client, "interactions", params, organism_id) if r["is_directed"]]
        linkers = pick_linkers(records, set(accs), max_linkers) if max_linkers else {}
        others: list[dict[str, Any]] = []
        if linkers:
            query = " OR ".join(f"accession:{a}" for a in linkers)
            res = await get(client, f"{UNIPROT_API}/search", {"query": query, "fields": NETWORK_FIELDS + ",gene_names"})
            res.raise_for_status()
            others = res.json()["results"]
        nodes = {e["primaryAccession"]: e for e in [*listed, *others]}

        # Modification sites, between enzymes annotated as such
        params = {"enzymes": ",".join(nodes), "substrates": ",".join(nodes), "enzyme_substrate": "AND"}
        params["fields"] = "sources,curation_effort"
        sites = await fetch_omnipath(client, "enz_sub", params, organism_id)

    regulations = [regulation_of(r, organism_id) for r in records if r["source"] in nodes and r["target"] in nodes]
    regulations.sort(key=lambda r: -r["evidence"])
    enzymes = {a for a, e in nodes.items() if ENZYME_KEYWORDS & {k["id"] for k in e.get("keywords", [])}}
    by_pair = {(r["source"], r["target"]): r for r in regulations}
    for s in sorted(sites, key=lambda s: -(s.get("curation_effort") or 0)):
        r = by_pair.get((s["enzyme"], s["substrate"]))
        if r and s["enzyme"] in enzymes and (s.get("curation_effort") or 0) >= 2 and len(r["sites"]) < 6:
            resources = list(dict.fromkeys(x.split("_")[0] for x in s.get("sources", [])))
            r["sites"].append(
                Site(label=f"{s['modification']} {s['residue_type']}{s['residue_offset']}", resources=resources)
            )
    for r in regulations:
        if r["sites"]:
            url = omnipath_url("enz_sub", [r["source"]], [r["target"]], organism_id)
            r["links"].append(Link(label="OmniPath sites", url=url))

    # Physical interactions of the entries, between the nodes
    physical: dict[frozenset[str], PhysicalInteraction] = {}
    for a, e in nodes.items():
        for c in e.get("comments", []):
            for i in c.get("interactions", []):
                b = i["interactantTwo"].get("uniProtKBAccession", "").split("-")[0]
                if b in nodes and b != a and frozenset((a, b)) not in physical:
                    physical[frozenset((a, b))] = PhysicalInteraction(
                        a=a,
                        b=b,
                        experiments=i["numberOfExperiments"],
                        links=[
                            Link(label="IntAct evidence (MITAB)", url=f"{INTACT_MIQL}/id:{a}%20AND%20id:{b}"),
                            Link(
                                label="UniProtKB interactions",
                                url=f"https://www.uniprot.org/uniprotkb/{a}/entry#interaction",
                            ),
                        ],
                    )

    # Reactome pathways shared by at least 2 nodes
    members: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for a, e in nodes.items():
        for x in e.get("uniProtKBCrossReferences", []):
            if x["database"] == "Reactome":
                members.setdefault(x["id"], []).append(a)
                names[x["id"]] = next((p["value"] for p in x["properties"] if p["key"] == "PathwayName"), x["id"])
    pathways = [
        Pathway(
            id=p,
            name=names[p],
            members=m,
            links=[Link(label="Reactome", url=f"https://reactome.org/content/detail/{p}")],
        )
        for p, m in members.items()
        if len(m) > 1
    ]
    pathways.sort(key=lambda p: (-len(p["members"]), p["name"]))

    # Paths from the source to the target, and feedback loops
    start = by_gene.get((source or genes[0]).upper(), accs[0])
    end = by_gene.get(target.upper()) if target else None
    graph: Graph = {}
    for r in regulations:
        graph.setdefault(r["source"], {})[r["target"]] = r["evidence"]
    paths = best_paths(graph, start, end) if end else []
    depth = signal_depth(graph, start)
    feedback = feedback_edges(regulations, graph, depth)

    data = NetworkData(
        organism=next((e.get("organism", {}).get("scientificName") for e in listed), None),
        source=start,
        target=end,
        nodes=[
            NetworkNode(
                accession=a,
                gene=gene_name(e),
                name=protein_name(e),
                listed=a in accs,
                via=linkers.get(a),
                depth=depth.get(a),
            )
            for a, e in nodes.items()
        ],
        regulations=regulations,
        interactions=sorted(physical.values(), key=lambda i: -i["experiments"]),
        pathways=pathways[:40],
        paths=paths,
        feedback=feedback,
        missing=missing,
        sources=network_sources(list(nodes), regulations, organism_id),
    )
    return text_result(network_text(data), data)


def network_sources(accs: list[str], regulations: list[Regulation], organism_id: int) -> list[DataSource]:
    """Where the data of the network comes from, with the queries of the data used"""
    resources = Counter(res for r in regulations for res in r["resources"])
    entries = " OR ".join(f"accession:{a}" for a in accs)
    return [
        DataSource(
            name="UniProtKB",
            provides="Reviewed protein entries: names, physical interactions (Interaction section) and Reactome "
            "pathways (cross-references), kinase and phosphatase keywords",
            url=str(httpx.URL("https://www.uniprot.org/uniprotkb", params={"query": entries})),
        ),
        DataSource(
            name="OmniPath interactions",
            provides="Directed regulations, combining "
            f"{len(resources)} resources: {', '.join(r for r, _ in resources.most_common())}",
            url=omnipath_url("interactions", accs, accs, organism_id),
        ),
        DataSource(
            name="OmniPath enzyme-substrate",
            provides="Modification sites of the regulations, kept when the enzyme is a kinase or phosphatase in "
            "UniProtKB",
            url=omnipath_url("enz_sub", accs, accs, organism_id),
        ),
        DataSource(
            name="IntAct",
            provides="Physical interactions and their number of experiments, as summarized in UniProtKB",
            url="https://www.ebi.ac.uk/intact/",
        ),
        DataSource(
            name="Reactome",
            provides="Pathways shared by at least 2 proteins, from UniProtKB",
            url="https://reactome.org",
        ),
    ]


def network_text(data: NetworkData) -> str:
    """Summary of the network for the model"""
    gene = {n["accession"]: n["gene"] for n in data["nodes"]}
    regs = {(r["source"], r["target"]): r for r in data["regulations"]}

    def reg(r: Regulation) -> str:
        effect = f"{r['effect']}, mostly {r['majority']}" if r["majority"] else r["effect"]
        sites = f"; {', '.join(s['label'] for s in r['sites'])}" if r["sites"] else ""
        more = f" +{len(r['resources']) - 4}" if len(r["resources"]) > 4 else ""
        resources = ", ".join(r["resources"][:4]) + more
        pmids = ", ".join(ref["pubmed"] for ref in r["references"][:3]) or "none"
        return (
            f"{gene[r['source']]} -> {gene[r['target']]} ({effect}; evidence {r['evidence']}{sites}; "
            f"resources {resources}; PMID {pmids})"
        )

    def chain(nodes: list[str]) -> str:
        return " ".join([gene[nodes[0]]] + [f"-{regs[(a, b)]['effect'][:3]}-> {gene[b]}" for a, b in pairwise(nodes)])

    linkers = [
        f"{n['gene']} ({' -> '.join(gene[a] for a in n['via'] or [])})" for n in data["nodes"] if not n["listed"]
    ]
    counts_by_effect = Counter(r["effect"] for r in data["regulations"])
    lines = [
        f"Shown to the user: network of {len(data['nodes'])} {data['organism']} proteins"
        + (
            f", with linkers added as they connect 2 listed proteins in OmniPath: {', '.join(linkers)}"
            if linkers
            else ""
        ),
    ]
    if data["missing"]:
        lines.append(f"No reviewed entry for: {', '.join(data['missing'])}")
    lines.append(
        f"Directed regulations from OmniPath ({len(data['regulations'])}: "
        f"{', '.join(f'{n} {k}' for k, n in counts_by_effect.most_common())}), evidence is the number of "
        "resource and reference pairs, mixed when both activation and inhibition are reported:"
    )
    lines += [f"- {reg(r)}" for r in data["regulations"][:60]]
    if len(data["regulations"]) > 60:
        lines.append(f"- +{len(data['regulations']) - 60} less supported")
    if data["target"]:
        found = "; ".join(chain(p) for p in data["paths"]) or "none"
        lines.append(
            f"Best supported directed paths (highest minimum evidence, then shortest) {gene[data['source']]} to {gene[data['target']]}: {found}"
        )
    lines.append(f"Feedback, edges going back upstream of {gene[data['source']]} and the loop they close:")
    lines += [
        f"- {reg(regs[(f['source'], f['target'])])}, loop: {chain([*f['loop'], f['target']])}"
        for f in data["feedback"][:15]
    ] or ["- none"]
    physical = "; ".join(
        f"{gene[i['a']]} - {gene[i['b']]} ({i['experiments']} experiments)" for i in data["interactions"][:40]
    )
    lines.append(f"Physical interactions from IntAct, via UniProtKB: {physical or 'none'}")
    shared = "; ".join(
        f"{p['name']} ({p['id']}): {', '.join(gene[m] for m in p['members'])}" for p in data["pathways"][:12]
    )
    lines.append(f"Reactome pathways shared, from UniProtKB cross-references: {shared or 'none'}")
    lines.append("Sources, with the queries of the data used:")
    lines += [f"- {s['name']}: {s['provides']} ({s['url']})" for s in data["sources"]]
    lines.append(
        "Paths, feedback loops, linkers and the mixed effect are computed by this tool from the OmniPath "
        "regulations, cite the resources and PubMed IDs of their edges"
    )
    lines.append(
        "The user can toggle the 3 kinds of relationships, filter by evidence, and click proteins, edges, paths "
        "or loops to highlight them and ask about them."
    )
    return "\n".join(lines)


def widget_html(name: str) -> str:
    """Widget HTML with the local scripts and stylesheets it references inlined"""
    html = (WIDGETS / name).read_text()
    html = re.sub(
        r'<script src="(\w+\.js)"></script>', lambda m: f"<script>\n{(WIDGETS / m[1]).read_text()}</script>", html
    )
    return re.sub(
        r'<link rel="stylesheet" href="(\w+\.css)" />',
        lambda m: f"<style>\n{(WIDGETS / m[1]).read_text()}</style>",
        html,
    )


apps.add_html_resource(
    "ui://uniprot/features.html",
    widget_html("features.html"),
    title="UniProt sequence features",
    csp=ResourceCsp(resource_domains=[CDN]),
)
apps.add_html_resource(
    "ui://uniprot/structure.html",
    widget_html("structure.html"),
    title="UniProt structure and features",
    csp=ResourceCsp(
        resource_domains=[CDN, "https://alphafold.ebi.ac.uk"],
        connect_domains=["https://alphafold.ebi.ac.uk", "https://www.ebi.ac.uk"],
    ),
)
apps.add_html_resource(
    "ui://uniprot/table.html",
    widget_html("table.html"),
    title="UniProt search results",
    csp=ResourceCsp(resource_domains=[CDN]),
)
apps.add_html_resource(
    "ui://uniprot/variants.html",
    widget_html("variants.html"),
    title="UniProt variant explorer",
    csp=ResourceCsp(resource_domains=[CDN]),
)
apps.add_html_resource(
    "ui://uniprot/matrix.html",
    widget_html("matrix.html"),
    title="UniProt annotation matrix",
    csp=ResourceCsp(resource_domains=[CDN]),
)
apps.add_html_resource(
    "ui://uniprot/network.html",
    widget_html("network.html"),
    title="Protein pathway and interaction network",
    csp=ResourceCsp(resource_domains=[CDN]),
)
