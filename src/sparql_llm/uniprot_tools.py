"""UniProt tools calling the UniProt REST API directly.

- Regular tools returning data to the model: `search_proteins` and `get_protein`
- Tools showing MCP Apps widgets: sequence features, 3D structure with features, search results table,
  variant explorer and annotation matrix. The widget gets the full data in `structuredContent`, the model only gets
  a text summary. Widgets are in `widgets/`, local scripts and stylesheets they reference are inlined when served.

Regular tools are added with `add_uniprot_tools(mcp)`, MCP Apps tools with `MCPServer(extensions=[apps])`.
"""

import asyncio
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent
from typing_extensions import TypedDict

UNIPROT_API = "https://rest.uniprot.org/uniprotkb"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction"
PROTEINS_API = "https://www.ebi.ac.uk/proteins/api"
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


def text_result(text: str, data: Mapping[str, Any]) -> CallToolResult:
    """Summary for the model, full data for the widget"""
    return CallToolResult(content=[TextContent(type="text", text=text)], structured_content=dict(data))


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT)


async def get(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """GET retried on timeouts and server errors, which are transient on the UniProt and AlphaFold APIs"""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            res = await client.get(url, params=params)
            if res.status_code < 500 or attempt == ATTEMPTS:
                return res
        except httpx.TransportError:
            if attempt == ATTEMPTS:
                raise RuntimeError(f"{url} did not answer after {ATTEMPTS} attempts, try again later") from None
        await asyncio.sleep(attempt)
    raise AssertionError("unreachable")


async def fetch_entry(client: httpx.AsyncClient, accession: str) -> dict[str, Any]:
    res = await get(client, f"{UNIPROT_API}/{accession.strip()}.json")
    if res.status_code in (400, 404):
        raise ValueError(f"UniProtKB entry {accession!r} not found")
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
        raise ValueError(f"Invalid query: {', '.join(res.json().get('messages', []))}")
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
@apps.tool(resource_uri="ui://uniprot/features.html")
async def show_protein_features(accession: str) -> CallToolResult:
    """Show the sequence features of a UniProtKB entry (e.g. P31749) to the user in an interactive track viewer,
    zoomable along the sequence: domains, sites, PTMs, signal peptides, topology, secondary structure and variants"""
    async with http_client() as client:
        e = await fetch_entry(client, accession)
    info, features = entry_info(e), features_of(e)
    text = f"Shown to the user: {len(features)} features of {entry_title(info)}\n{features_text(features)}"
    return text_result(text, FeaturesData(**info, features=features))


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
        raise ValueError(f"No AlphaFold model or PDB entry for {accession}")
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
            raise ValueError(f"Invalid query: {', '.join(res.json().get('messages', []))}")
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
async def show_protein_variants(accession: str) -> CallToolResult:
    """Show the disease and natural variants of a UniProtKB entry (e.g. P04637) to the user in an interactive
    explorer: variants positioned on the sequence next to domains, filterable by consequence, clinical significance,
    evidence and disease, with links to ClinVar, dbSNP and publications"""
    async with http_client() as client:
        e, raw = await asyncio.gather(fetch_entry(client, accession), fetch_variants(client, accession))
    info = entry_info(e)
    variants = sorted((variant_of(v) for v in raw), key=variant_rank, reverse=True)[:MAX_VARIANTS]
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
    return text_result(text, VariantsData(**info, features=domains, variants=variants, total=len(raw)))


def go_level(evidence_type: str) -> int:
    code = evidence_type.split(":")[0]
    return 3 if code in GO_EXPERIMENTAL else 1 if code == "IEA" else 2


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
    gene = next((g["geneName"]["value"] for g in e.get("genes", []) if "geneName" in g), e["primaryAccession"])
    return MatrixProtein(accession=e["primaryAccession"], gene=gene, name=protein_name(e), terms=annotations)


@apps.tool(resource_uri="ui://uniprot/matrix.html")
async def show_annotation_matrix(genes: list[str], organism_id: int = 9606) -> CallToolResult:
    """Show a heatmap of the reviewed UniProtKB entries of a gene list (e.g. ["TP53", "MDM2", "CDKN1A"]) by their
    GO terms, keywords or Reactome pathways to the user, for a quick functional overview of the list.
    `organism_id` is the NCBI taxonomy ID, human by default"""
    genes = list(dict.fromkeys(g.strip() for g in genes if g.strip()))[:100]
    if not genes:
        raise ValueError("No gene given")
    query = f"({' OR '.join(f'gene_exact:{g}' for g in genes)}) AND organism_id:{organism_id} AND reviewed:true"
    params = {
        "query": query,
        "size": 500,
        "fields": "accession,gene_primary,protein_name,organism_name,go,keyword,xref_reactome",
    }
    async with http_client() as client:
        res = await get(client, f"{UNIPROT_API}/search", params)
    if res.status_code == 400:
        raise ValueError(f"Invalid gene list: {', '.join(res.json().get('messages', []))}")
    res.raise_for_status()
    results = res.json()["results"]

    # One entry per gene, the one with it as primary name, else matching a synonym
    terms: dict[str, Term] = {}
    proteins: list[MatrixProtein] = []
    missing = []
    for gene in genes:
        names = [{g["geneName"]["value"].upper() for g in e.get("genes", []) if "geneName" in g} for e in results]
        synonyms = [{s["value"].upper() for g in e.get("genes", []) for s in g.get("synonyms", [])} for e in results]
        entry = next((e for e, n in zip(results, names, strict=True) if gene.upper() in n), None) or next(
            (e for e, n in zip(results, synonyms, strict=True) if gene.upper() in n), None
        )
        if entry and all(p["accession"] != entry["primaryAccession"] for p in proteins):
            proteins.append(matrix_protein(entry, terms))
        elif not entry:
            missing.append(gene)
    if not proteins:
        raise ValueError(f"No reviewed UniProtKB entry for {', '.join(genes)} in organism {organism_id}")
    organism = next((e.get("organism", {}).get("scientificName") for e in results), None)

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
apps.add_html_resource("ui://uniprot/table.html", widget_html("table.html"), title="UniProt search results")
apps.add_html_resource(
    "ui://uniprot/variants.html",
    widget_html("variants.html"),
    title="UniProt variant explorer",
    csp=ResourceCsp(resource_domains=[CDN]),
)
apps.add_html_resource("ui://uniprot/matrix.html", widget_html("matrix.html"), title="UniProt annotation matrix")
