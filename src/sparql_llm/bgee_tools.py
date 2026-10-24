"""Bgee gene expression tool showing a MCP Apps widget, calling the Bgee JSON API (https://www.bgee.org/api/) directly.

`show_gene_expression` shows a heatmap of anatomical entities by gene, colored by the Bgee expression score.
"""

import asyncio
from typing import Any, Literal

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from typing_extensions import TypedDict

from sparql_llm.uniprot_tools import READ_ONLY, apps, get, http_client, text_result, widget_html

BGEE_API = "https://www.bgee.org/api/"
# Bgee data types, as named by the expression calls of a gene
DATA_TYPES = ["RNA-Seq", "single-cell RNA-Seq", "Affymetrix", "in situ hybridization", "EST"]
DataType = Literal["RNA-Seq", "single-cell RNA-Seq", "Affymetrix", "in situ hybridization", "EST"]
# Data types of the organ systems summary call, keyed by their enum
SUMMARY_TYPES = {
    "RNA_SEQ": "RNA-Seq",
    "SC_RNA_SEQ": "single-cell RNA-Seq",
    "AFFYMETRIX": "Affymetrix",
    "IN_SITU": "in situ hybridization",
    "EST": "EST",
}
NO_CELL_TYPE = "GO:0005575"
MAX_GENES = 20


# Data sent to the widget in `structuredContent`, as read by `widgets/expression.html`
class Condition(TypedDict):
    anatId: str
    anatName: str
    cellId: str | None
    cellName: str | None


class ExpressionCall(TypedDict):
    score: float
    """Expression score from 0 to 100, a normalized rank of the gene in the condition"""
    confidence: str | None
    fdr: str | None
    quality: str
    """gold, silver or bronze"""
    expressed: bool
    dataTypes: list[str]


class ExpressionGene(TypedDict):
    id: str
    name: str
    description: str | None
    calls: dict[str, ExpressionCall]
    """Calls by condition key, expressed and not expressed"""
    systems: dict[str, ExpressionCall]
    """Expressed calls in organ systems, by condition key"""


class ExpressionFilters(TypedDict):
    """Filters of the heatmap when it opens"""

    systems: bool
    """Organ systems instead of all anatomical entities and cell types"""
    dataType: str | None
    gold: bool
    absent: bool
    """Not expressed calls shown"""
    search: str


class ExpressionData(TypedDict):
    species: dict[str, Any]
    genes: list[ExpressionGene]
    conditions: dict[str, Condition]
    missing: list[str]
    filters: ExpressionFilters


async def bgee(client: httpx.AsyncClient, params: list[tuple[str, Any]]) -> dict[str, Any]:
    res = await get(client, BGEE_API, params=[("display_type", "json"), *params])
    if res.status_code >= 400:
        raise ToolError(f"Bgee API error {res.status_code}: {res.text[:300]}")
    return res.json()["data"]


async def find_gene(client: httpx.AsyncClient, query: str, species_id: int) -> dict[str, Any] | None:
    """Bgee gene with this Ensembl ID or name in the species, else the first gene with it as synonym"""
    data = await bgee(client, [("page", "gene"), ("query", query.strip()), ("species_id", species_id), ("limit", 10)])
    matches = data["result"]["geneMatches"]
    q = query.strip().lower()
    exact = [m for m in matches if q in (m["gene"]["geneId"].lower(), m["gene"]["name"].lower())]
    best = exact or matches
    return best[0]["gene"] if best else None


def condition_key(c: dict[str, Any]) -> tuple[str, Condition]:
    anat = c["anatEntity"]
    cell = c.get("cellType")
    if cell and cell["id"] == NO_CELL_TYPE:
        cell = None
    key = f"{anat['id']}|{cell['id']}" if cell else anat["id"]
    return key, Condition(
        anatId=anat["id"],
        anatName=anat["name"],
        cellId=cell["id"] if cell else None,
        cellName=cell["name"] if cell else None,
    )


def expression_call(c: dict[str, Any], data_types: list[str]) -> ExpressionCall:
    score = c.get("expressionScore") or {}
    return ExpressionCall(
        score=float(score.get("expressionScore") or 0),
        confidence=score.get("expressionScoreConfidence"),
        fdr=c.get("fdr"),
        quality=c.get("expressionQuality", ""),
        expressed=c.get("expressionState") == "expressed",
        dataTypes=data_types,
    )


async def gene_calls(client: httpx.AsyncClient, gene_id: str, species_id: int, absent: bool) -> list[dict[str, Any]]:
    """Expressed or not expressed calls of a gene in anatomical entities and cell types, all data types"""
    params: list[tuple[str, Any]] = [
        ("page", "gene"),
        ("action", "expression"),
        ("gene_id", gene_id),
        ("species_id", species_id),
        ("cond_param", "anat_entity"),
        ("cond_param", "cell_type"),
        ("data_type", "all"),
    ]
    if absent:
        params.append(("expr_type", "not_expressed"))
    return (await bgee(client, params))["calls"]


async def summary_calls(client: httpx.AsyncClient, gene_ids: list[str], species_id: int) -> list[dict[str, Any]]:
    """Expressed calls of the genes in about 16 organ systems, as shown first by the Bgee expression graph"""
    params: list[tuple[str, Any]] = [
        ("page", "data"),
        ("action", "expr_calls"),
        ("get_results", 1),
        ("offset", 0),
        ("limit", 10000),
        ("species_id", species_id),
        *[("gene_id", g) for g in gene_ids],
        ("anat_entity_id", "SUMMARY"),
        ("cell_type_id", "SUMMARY"),
        ("cond_param2", "anat_entity"),
        ("data_qual", "BRONZE"),
        *[("data_type", t) for t in SUMMARY_TYPES],
    ]
    return (await bgee(client, params))["expressionData"]["expressionCalls"]


@apps.tool(resource_uri="ui://bgee/expression.html", annotations=READ_ONLY)
async def show_gene_expression(
    genes: list[str],
    species_id: int = 9606,
    organ_systems: bool = False,
    data_type: DataType | None = None,
    gold_only: bool = False,
    show_absent: bool = True,
    search: str | None = None,
) -> CallToolResult:
    """Show where genes are expressed to the user, as a heatmap of anatomical entities and cell types by gene colored
    by the Bgee expression score (0-100), with organ systems, data types (RNA-Seq, scRNA-Seq, Affymetrix, in situ,
    EST), call quality and absence of expression. `genes` are gene symbols or Ensembl IDs (e.g. ["TP53", "MDM2"]),
    of the species with NCBI taxonomy ID `species_id`, human by default (mouse is 10090, zebrafish 7955).
    Filters set when the heatmap opens, the user can change them: `organ_systems` to show organ systems instead of
    all anatomical entities, only the calls with a `data_type`, `gold_only` quality calls, `show_absent` false to hide
    not expressed calls, and a `search` text found in the anatomical entities and cell types (e.g. "brain")"""
    if not genes:
        raise ToolError("Give at least one gene")
    async with http_client() as client:
        found = await asyncio.gather(*[find_gene(client, g, species_id) for g in genes[:MAX_GENES]])
        resolved = {g["geneId"]: g for g in found if g}
        missing = [q for q, g in zip(genes, found, strict=False) if not g]
        if not resolved:
            raise ToolError(f"No Bgee gene found for {', '.join(genes)} in species {species_id}")
        ids = list(resolved)
        # Expressed and not expressed calls of each gene, and organ systems of all genes
        calls = await asyncio.gather(
            *[gene_calls(client, g, species_id, absent) for g in ids for absent in (False, True)],
            summary_calls(client, ids, species_id),
        )

    conditions: dict[str, Condition] = {}
    out: list[ExpressionGene] = []
    for i, gene_id in enumerate(ids):
        info = resolved[gene_id]
        gene_calls_by_cond: dict[str, ExpressionCall] = {}
        for c in [*calls[2 * i], *calls[2 * i + 1]]:
            key, cond = condition_key(c["condition"])
            conditions[key] = cond
            gene_calls_by_cond.setdefault(key, expression_call(c, c.get("dataTypesWithData", [])))
        out.append(
            ExpressionGene(
                id=gene_id, name=info["name"], description=info.get("description"), calls=gene_calls_by_cond, systems={}
            )
        )
    by_id = {g["id"]: g for g in out}
    for c in calls[-1]:
        key, cond = condition_key(c["condition"])
        conditions[key] = cond
        types = [SUMMARY_TYPES[t] for t, present in c.get("dataTypesWithData", {}).items() if present]
        if c["gene"]["geneId"] in by_id:
            by_id[c["gene"]["geneId"]]["systems"][key] = expression_call(c, types)
    sp = next(iter(resolved.values()))["species"]
    species = {"id": sp["id"], "name": f"{sp['genus']} {sp['speciesName']}", "commonName": sp.get("name")}

    # Summary for the model: top anatomical entities of each gene, and organ systems
    def label(key: str) -> str:
        c = conditions[key]
        return f"{c['anatName']} ({c['anatId']})" + (f" / {c['cellName']} ({c['cellId']})" if c["cellId"] else "")

    lines = [f"Shown to the user: Bgee expression of {len(out)} genes in {species['name']}"]
    if missing:
        lines.append(f"No Bgee gene found for: {', '.join(missing)}")
    for g in out:
        expressed = sorted(
            ((k, c) for k, c in g["calls"].items() if c["expressed"]), key=lambda kc: kc[1]["score"], reverse=True
        )
        absent = [k for k, c in g["calls"].items() if not c["expressed"]]
        top = "; ".join(f"{label(k)} {c['score']:.1f}" for k, c in expressed[:12])
        systems = "; ".join(
            f"{conditions[k]['anatName']} {c['score']:.1f}"
            for k, c in sorted(g["systems"].items(), key=lambda kc: kc[1]["score"], reverse=True)
        )
        lines.append(
            f"\n{g['name']} ({g['id']}, {g['description']}): expressed in {len(expressed)} conditions, "
            f"not expressed in {len(absent)}\n- Highest expression scores: {top or 'none'}"
            f"\n- Organ systems: {systems or 'none'}"
        )
        if absent:
            lines.append(f"- Not expressed in: {', '.join(conditions[k]['anatName'] for k in absent[:15])}")
    filters = ExpressionFilters(
        systems=organ_systems, dataType=data_type, gold=gold_only, absent=show_absent, search=search or ""
    )
    given = [
        label
        for label, on in [
            ("organ systems shown", organ_systems),
            (f"only {data_type} data", bool(data_type)),
            ("only gold quality calls", gold_only),
            ("not expressed calls hidden", not show_absent),
            (f"anatomical entities matching '{search}'", bool(search)),
        ]
        if on
    ]
    if given:
        lines.append(f"\nFilters set in the heatmap: {', '.join(given)}")
    lines.append(
        "\nThe user can switch between organ systems and all anatomical entities, filter by data type and quality, "
        "and click a condition or a gene to ask about it."
    )
    return text_result(
        "\n".join(lines),
        ExpressionData(species=species, genes=out, conditions=conditions, missing=missing, filters=filters),
    )


apps.add_html_resource(
    "ui://bgee/expression.html",
    widget_html("expression.html"),
    title="Bgee gene expression",
)
