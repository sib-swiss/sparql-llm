"""Cellosaurus cell line tool showing a MCP Apps widget, calling the Cellosaurus API (https://api.cellosaurus.org) and
its CLASTR STR similarity search directly.

`show_cell_line` shows a cell line: identity, problematic (contaminated or misidentified) warnings, hierarchy, genome
ancestry, mutations, HLA typing, and its STR profile next to the cell lines with the most similar profiles.
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

CELLOSAURUS_API = "https://api.cellosaurus.org"
CLASTR_API = "https://www.cellosaurus.org/str-search/api/query"
CVCL = re.compile(r"^\s*(CVCL_[A-Z0-9]{4})\s*$", re.IGNORECASE)
# Fields of a cell line, without the cross-references and publications that make most of its size
FIELDS = "id,ac,sy,ox,sx,ag,ca,di,hi,ch,oi,str,var,anc,hla,cc,dt,dtc,msi,transformant,derived-from-site"
# Species of the STR profiles searched by CLASTR
CLASTR_SPECIES = {"9606": "human", "10090": "mouse", "9615": "dog"}
MAX_CHILDREN = 60
MAX_MATCHES = 25


# Data sent to the widget in `structuredContent`, as read by `widgets/cellline.html`
class Ref(TypedDict):
    id: str
    name: str


class StrMarker(TypedDict):
    name: str
    alleles: str
    """Alleles of the first source, e.g. 9,10"""
    conflict: bool
    variants: list[dict[str, Any]]
    """Alleles reported by each source when they conflict"""


class Mutation(TypedDict):
    type: str
    """Mutation, Gene fusion, Gene deletion..."""
    genes: list[str]
    description: str | None
    zygosity: str | None
    clinvar: str | None
    pubmed: list[str]


class StrMatch(TypedDict):
    accession: str
    name: str
    species: str | None
    score: float
    problematic: bool
    problem: str | None
    markers: dict[str, list[dict[str, Any]]]
    """Alleles of each marker of the best profile, with `matched` when compared with the query"""


class CellLineData(TypedDict):
    accession: str
    name: str
    synonyms: list[str]
    category: str | None
    species: list[Ref]
    sex: str | None
    age: str | None
    diseases: list[Ref]
    site: str | None
    parents: list[Ref]
    children: list[Ref]
    childrenTotal: int
    sameOrigin: list[Ref]
    problematic: str | None
    """Why the cell line is contaminated or misidentified"""
    registrations: list[str]
    comments: list[dict[str, str]]
    strSources: list[str]
    markers: list[StrMarker]
    matches: list[StrMatch]
    """Cell lines with the most similar STR profiles, from CLASTR"""
    mutations: list[Mutation]
    ancestry: list[dict[str, Any]]
    """Genome ancestry, percentage per population"""
    hla: list[dict[str, Any]]
    doublingTime: str | None
    msi: str | None
    transformants: list[str]


async def cellosaurus(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> httpx.Response:
    res = await get(client, f"{CELLOSAURUS_API}/{path}", params)
    if res.status_code >= 500:
        raise ToolError(f"Cellosaurus API error {res.status_code}: {res.text[:300]}")
    return res


def normalize(name: str) -> str:
    return re.sub(r"[\s\-_.]", "", name).lower()


async def find_cell_line(client: httpx.AsyncClient, query: str) -> tuple[str, list[str]]:
    """Accession from an accession or a name, the search ranks synonyms poorly: exact names first"""
    if m := CVCL.match(query):
        return m[1].upper(), []
    q = query.strip().replace('"', "")
    # Names and synonyms, each search misses exact names among many derived lines (e.g. HeLa KO lines), else any field
    found: dict[str, dict[str, Any]] = {}
    for searches in ((f'id:"{q}"', f'sy:"{q}"', f'idsy:"{q}"'), (f'"{q}"',)):
        responses = await asyncio.gather(
            *[
                cellosaurus(client, "search/cell-line", {"q": s, "format": "json", "fields": "id,ac,sy", "rows": 100})
                for s in searches
            ]
        )
        for res in responses:
            for c in res.json().get("Cellosaurus", {}).get("cell-line-list", []) if res.status_code == 200 else []:
                found.setdefault(c["accession-list"][0]["value"], c)
        if found:
            break
    lines = list(found.values())
    if not lines:
        raise ToolError(f"No Cellosaurus cell line found for {query!r}")
    target = normalize(q)

    def names(c: dict[str, Any], kind: str) -> list[str]:
        return [normalize(n["value"]) for n in c.get("name-list", []) if n["type"] == kind]

    lines.sort(key=lambda c: (target not in names(c, "identifier"), target not in names(c, "synonym")))
    hits = [f"{c['accession-list'][0]['value']} {names_of(c)[0]}" for c in lines[1:8]]
    return lines[0]["accession-list"][0]["value"], hits


def names_of(c: dict[str, Any]) -> list[str]:
    return [n["value"] for n in c.get("name-list", [])]


def ref(x: dict[str, Any]) -> Ref:
    """Cell line reference, from the different shapes of the child, parent and same origin lists"""
    acc = x.get("accession")
    name = x.get("name") or x.get("label")
    return Ref(
        id=acc["value"] if isinstance(acc, dict) else str(acc),
        name=name["value"] if isinstance(name, dict) else str(name),
    )


def pubmed_of(sources: list[dict[str, Any]]) -> list[str]:
    refs = [s.get("reference", {}).get("resource-internal-ref", "") for s in sources]
    return [r.removeprefix("PubMed=") for r in refs if r.startswith("PubMed=")]


def source_name(s: dict[str, Any]) -> str:
    if "xref" in s:
        return s["xref"].get("database", "")
    return s.get("reference", {}).get("resource-internal-ref") or s.get("value", "")


def markers_of(str_list: dict[str, Any]) -> list[StrMarker]:
    markers = []
    for m in str_list.get("marker-list", []):
        data = m.get("marker-data-list", [])
        markers.append(
            StrMarker(
                name=m["id"],
                alleles=data[0].get("marker-alleles", "") if data else "",
                conflict=m.get("conflict") == "true",
                variants=[
                    {
                        "alleles": d.get("marker-alleles", ""),
                        "sources": [source_name(s) for s in d.get("source-list", [])],
                    }
                    for d in data
                ]
                if len(data) > 1
                else [],
            )
        )
    return markers


def mutation_of(v: dict[str, Any]) -> Mutation:
    xrefs = v.get("xref-list", [])
    return Mutation(
        type=v.get("variation-type", ""),
        genes=[x["label"] for x in xrefs if x.get("database") in ("HGNC", "MGI", "RGD", "VGNC") and x.get("label")],
        description=v.get("mutation-description"),
        zygosity=v.get("zygosity-type"),
        clinvar=next((x["accession"] for x in xrefs if x.get("database") == "ClinVar"), None),
        pubmed=pubmed_of(v.get("source-list", [])),
    )


async def str_matches(client: httpx.AsyncClient, markers: list[StrMarker], species: str) -> list[StrMatch]:
    """Cell lines with the most similar STR profiles, Tanabe score as on the CLASTR website"""
    params: dict[str, Any] = {m["name"]: m["alleles"] for m in markers if m["alleles"]}
    params.update({"species": species, "maxResults": MAX_MATCHES, "outputFormat": "json"})
    try:
        res = await get(client, CLASTR_API, params)
        res.raise_for_status()
    except (httpx.HTTPError, ToolError):
        return []
    matches = []
    for r in res.json().get("results", []):
        profile = (r.get("profiles") or [{}])[0]
        matches.append(
            StrMatch(
                accession=r["accession"],
                name=r["name"],
                species=r.get("species"),
                score=float(r.get("bestScore") or 0),
                problematic=bool(r.get("problematic")),
                problem=r.get("problem"),
                markers={
                    m["name"]: [{"value": a["value"], "matched": a.get("matched")} for a in m.get("alleles", [])]
                    for m in profile.get("markers", [])
                },
            )
        )
    return matches


@apps.tool(resource_uri="ui://cellosaurus/cellline.html", annotations=READ_ONLY)
async def show_cell_line(cell_line: str) -> CallToolResult:
    """Show a cell line of Cellosaurus to the user: identity (species, sex, age, disease, site), warnings when it is
    contaminated or misidentified, its parent, children and lines from the same individual, genome ancestry, mutations,
    HLA typing, and its STR profile next to the cell lines with the most similar profiles (CLASTR), to check its
    authenticity. `cell_line` is a Cellosaurus accession (e.g. CVCL_0030) or a cell line name (e.g. HeLa, A-549, MCF-7)"""
    async with http_client() as client:
        accession, others = await find_cell_line(client, cell_line)
        res = await cellosaurus(client, f"cell-line/{accession}", {"format": "json", "fields": FIELDS})
        if res.status_code != 200:
            raise ToolError(f"Cellosaurus cell line {accession} not found")
        c = res.json()["Cellosaurus"]["cell-line-list"][0]
        markers = markers_of(c.get("str-list", {}))
        species = [Ref(id=s["accession"], name=s["label"]) for s in c.get("species-list", [])]
        clastr = next((CLASTR_SPECIES[s["id"]] for s in species if s["id"] in CLASTR_SPECIES), None)
        matches = await str_matches(client, markers, clastr) if markers and clastr else []

    names = c.get("name-list", [])
    comments = [{"category": x["category"], "value": x["value"]} for x in c.get("comment-list", [])]
    children = c.get("child-list", [])
    ancestry = c.get("genome-ancestry", {})
    site = next((s["site"].get("value") for s in c.get("derived-from-site-list", []) if "site" in s), None)
    data = CellLineData(
        accession=accession,
        name=next((n["value"] for n in names if n["type"] == "identifier"), accession),
        synonyms=[n["value"] for n in names if n["type"] == "synonym"],
        category=c.get("category"),
        species=species,
        sex=c.get("sex"),
        age=c.get("age"),
        diseases=[Ref(id=d["accession"], name=d["label"]) for d in c.get("disease-list", [])],
        site=site,
        parents=[ref(x) for x in c.get("derived-from", [])],
        children=[ref(x) for x in children[:MAX_CHILDREN]],
        childrenTotal=len(children),
        sameOrigin=[ref(x) for x in c.get("same-origin-as", [])],
        problematic=next((x["value"] for x in comments if x["category"] == "Problematic cell line"), None),
        registrations=[f"{r.get('registration-number')} ({r.get('registry')})" for r in c.get("registration-list", [])],
        comments=[x for x in comments if x["category"] not in ("Problematic cell line", "Part of")],
        strSources=[source_name(s) for s in c.get("str-list", {}).get("source-list", [])],
        markers=markers,
        matches=matches,
        mutations=[mutation_of(v) for v in c.get("sequence-variation-list", [])],
        ancestry=[
            {"population": p["population-name"], "percentage": float(p["population-percentage"])}
            for p in ancestry.get("population-list", [])
        ],
        hla=[
            {
                "source": source_name(h.get("source", {})),
                "alleles": [{"gene": a["gene"], "alleles": a["alleles"]} for a in h.get("hla-gene-alleles-list", [])],
            }
            for h in c.get("hla-typing-list", [])
        ],
        doublingTime=", ".join(d.get("doubling-time-value", "") for d in c.get("doubling-time-list", [])) or None,
        msi=next((m.get("msi-value") for m in c.get("microsatellite-instability-list", [])), None),
        transformants=[t.get("xref", {}).get("label") or t.get("value", "") for t in c.get("transformant-list", [])],
    )

    # Summary for the model
    def refs(values: list[Ref]) -> str:
        return "; ".join(f"{r['id']} {r['name']}" for r in values) or "none"

    lines = [
        f"Shown to the user: Cellosaurus {accession} {data['name']} ({data['category']}), "
        f"{', '.join(s['name'] for s in species)}, sex {data['sex']}, age {data['age']}",
        f"Disease: {refs(data['diseases'])}; site: {site}",
        f"Synonyms: {', '.join(data['synonyms'][:15]) or 'none'}",
    ]
    if data["problematic"]:
        lines.append(f"PROBLEMATIC: {data['problematic']} {'; '.join(data['registrations'])}")
    lines += [
        f"Parent: {refs(data['parents'])}; same individual: {refs(data['sameOrigin'])}",
        f"{data['childrenTotal']} children: {refs(data['children'][:15])}",
        "Genome ancestry: " + (", ".join(f"{a['population']} {a['percentage']}%" for a in data["ancestry"]) or "none"),
        "Mutations: "
        + (
            "; ".join(
                f"{', '.join(m['genes'])} {m['description'] or m['type']} ({m['zygosity'] or 'zygosity unknown'})"
                for m in data["mutations"][:30]
            )
            or "none"
        ),
        "HLA: "
        + ("; ".join(f"{a['gene']} {a['alleles']}" for a in data["hla"][0]["alleles"]) if data["hla"] else "none"),
        f"Doubling time: {data['doublingTime']}; MSI: {data['msi']}",
        "STR profile: " + ("; ".join(f"{m['name']} {m['alleles']}" for m in markers) or "none"),
        "Most similar STR profiles (CLASTR, Tanabe score): "
        + (
            "; ".join(
                f"{m['accession']} {m['name']} {m['score']:.1f}{' PROBLEMATIC' if m['problematic'] else ''}"
                for m in matches[:12]
            )
            or "none"
        ),
    ]
    lines += [f"{x['category']}: {x['value']}" for x in data["comments"][:10]]
    if others:
        lines.append(f"Other cell lines matching the name, not shown: {'; '.join(others)}")
    lines.append("The user can browse the STR matches, mutations, HLA and hierarchy, and click them to ask about them.")
    return text_result("\n".join(lines), data)


apps.add_html_resource(
    "ui://cellosaurus/cellline.html",
    widget_html("cellline.html"),
    title="Cellosaurus cell line",
    csp=ResourceCsp(resource_domains=[CDN]),
)
