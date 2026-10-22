"""MetaNetX tool showing a MCP Apps widget, querying the MetaNetX SPARQL endpoint (https://rdf.metanetx.org/sparql).

`show_metanetx` shows a MNXref chemical or reaction: the reconciliation of its identifiers in other databases as a
graph, with for chemicals their structure, isomers and reactions, and for reactions their participants and the
genome-scale metabolic models containing them.
"""

import asyncio
import re
from typing import Any

import httpx
from mcp.server.apps import ResourceCsp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from typing_extensions import TypedDict

from sparql_llm.uniprot_tools import CDN, READ_ONLY, apps, http_client, text_result, widget_html

MNX_SPARQL = "https://rdf.metanetx.org/sparql"
MNX_WEB = "https://www.metanetx.org"
CHEM = "https://rdf.metanetx.org/chem/"
REAC = "https://rdf.metanetx.org/reac/"
PREFIXES = """PREFIX mnx: <https://rdf.metanetx.org/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
MNX_ID = re.compile(r"^\s*(MNX[MR]\d+)\s*$", re.IGNORECASE)
# Databases by the prefix of their identifiers in MetaNetX
DATABASES = {
    "chebi": "ChEBI",
    "keggC": "KEGG",
    "keggD": "KEGG Drug",
    "keggG": "KEGG Glycan",
    "keggE": "KEGG",
    "biggM": "BiGG",
    "seedM": "SEED",
    "metacycM": "MetaCyc",
    "hmdb": "HMDB",
    "vmhM": "VMH",
    "sabiorkM": "SABIO-RK",
    "reactomeM": "Reactome",
    "envipathM": "enviPath",
    "lipidmaps": "LIPID MAPS",
    "slm": "SwissLipids",
    "rh": "Rhea",
    "keggR": "KEGG",
    "biggR": "BiGG",
    "seedR": "SEED",
    "metacycR": "MetaCyc",
    "sabiorkR": "SABIO-RK",
    "vmhR": "VMH",
}
MAX_REACTIONS = 40


# Data sent to the widget in `structuredContent`, as read by `widgets/metanetx.html`
class Chemical(TypedDict):
    id: str
    name: str
    formula: str | None
    charge: int | None
    mass: float | None
    inchikey: str | None
    smiles: str | None
    image: str | None
    """SVG depiction URL, for chemicals with a structure"""


class Xref(TypedDict):
    db: str
    id: str
    url: str | None
    name: str | None
    inchikey: str | None
    status: str
    """How it is reconciled: identical structure, other protonation, other stereo, different structure,
    no structure, obsolete (a secondary or deprecated identifier), or reaction"""


class Isomer(TypedDict):
    id: str
    name: str
    relation: str
    """parent (less defined, e.g. without stereo) or child"""


class ReactionRow(TypedDict):
    id: str
    equation: str
    ec: list[str]
    rhea: list[str]
    models: int


class Participant(Chemical):
    side: str
    coef: float
    compartment: str
    compartmentName: str | None


class Model(TypedDict):
    id: str
    organism: str | None
    taxId: str | None
    reaction: str | None
    """ID of the reaction in the model"""
    enzymes: list[str]
    """UniProtKB accessions of the enzymes catalyzing the reaction in the model"""


class MetaNetXData(TypedDict):
    kind: str
    """chemical or reaction"""
    id: str
    name: str
    reference: str | None
    """Identifier MNXref used as reference for the entity"""
    xrefs: list[Xref]
    chemical: Chemical | None
    isomers: list[Isomer]
    reactions: list[ReactionRow]
    """Reactions of the chemical in the most models"""
    reactionTotal: int
    participants: list[Participant]
    ec: list[str]
    balanced: bool | None
    transport: bool | None
    models: list[Model]


async def sparql(client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
    res = await client.post(
        MNX_SPARQL, data={"query": PREFIXES + query}, headers={"Accept": "application/sparql-results+json"}
    )
    if res.status_code != 200:
        raise ToolError(f"MetaNetX SPARQL endpoint error {res.status_code}: {res.text[:300]}")
    return [{k: v["value"] for k, v in b.items()} for b in res.json()["results"]["bindings"]]


def local(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def image_url(mnx_id: str, smiles: str | None) -> str | None:
    """MetaNetX depiction, chemicals without structure get a placeholder"""
    return f"{MNX_WEB}/cgi-bin/mnxget/chem_img/{mnx_id}.svg" if smiles else None


def to_int(v: str | None) -> int | None:
    return int(float(v)) if v not in (None, "") else None


async def resolve(client: httpx.AsyncClient, query: str) -> tuple[str, list[str]]:
    """MNXref ID from a MNX ID, an external identifier (e.g. chebi:15422, kegg.reaction:R00703) or a chemical
    name, with the other names matched"""
    if m := MNX_ID.match(query):
        return m[1].upper(), []
    if ":" in query and " " not in query.strip():
        # Identifiers.org prefixes or MetaNetX ones, mapped by MetaNetX
        for index in ("chem", "reac"):
            res = await client.post(
                f"{MNX_WEB}/map/ids",
                data={"query_list": query.strip(), "query_index": index, "output_format": "JSON"},
            )
            mapped: dict[str, Any] = next(iter(res.json().values()), {}) if res.status_code == 200 else {}
            if mapped.get("mnx_id"):
                return mapped["mnx_id"], []
    # Chemical names and synonyms, with the Virtuoso full text index, shortest names first
    term = re.sub(r"[\"'\\]", " ", query).strip()
    rows = await sparql(
        client,
        f"""SELECT ?chem ?name WHERE {{
          {{ SELECT DISTINCT ?chem WHERE {{
              {{ ?chem rdfs:comment ?m . ?m bif:contains '"{term}"' }}
              UNION {{ ?xref rdfs:comment ?m . ?m bif:contains '"{term}"' . ?chem mnx:chemXref ?xref }}
              ?chem a mnx:CHEM }} LIMIT 200 }}
          ?chem rdfs:comment ?name . FILTER(STRSTARTS(STR(?chem), "{CHEM}"))
        }} ORDER BY STRLEN(?name) LIMIT 50""",
    )
    if not rows:
        raise ToolError(f"No MetaNetX chemical or reaction found for {query!r}")
    # Exact names first, then names containing the term, then synonyms, shortest first
    t = term.lower()
    rows.sort(key=lambda r: (r["name"].lower() != t, t not in r["name"].lower(), len(r["name"])))
    return local(rows[0]["chem"]), [f"{local(r['chem'])} {r['name']}" for r in rows[1:8]]


def xref_status(ik: str | None, ref_ik: str | None, comment: str | None) -> str:
    """Reconciliation of a chemical identifier, from its InChIKey compared with the MetaNetX one"""
    if comment and "secondary/obsolete" in comment:
        return "obsolete"
    if not ik:
        return "no structure"
    if not ref_ik or ik == ref_ik:
        return "identical structure"
    if ik[:-1] == ref_ik[:-1]:
        return "other protonation"
    if ik[:14] == ref_ik[:14]:
        return "other stereo"
    return "different structure"


async def fetch_xrefs(client: httpx.AsyncClient, iri: str, prop: str, ref_ik: str | None) -> list[Xref]:
    """Identifiers of the entity in the source databases, without the identifiers.org duplicates"""
    rows = await sparql(
        client,
        f"""SELECT ?xref ?label ?desc ?ik ?src WHERE {{
          <{iri}> mnx:{prop} ?xref . ?xref rdfs:label ?label .
          FILTER(!STRSTARTS(STR(?xref), "https://identifiers.org/"))
          OPTIONAL {{ ?xref rdfs:comment ?desc }} OPTIONAL {{ ?xref mnx:stdInChIKey ?ik }}
          OPTIONAL {{ ?xref mnx:srcName ?src }}
        }}""",
    )
    xrefs: dict[str, Xref] = {}
    for r in rows:
        prefix, _, ident = r["label"].partition(":")
        if r["xref"] in xrefs or prefix not in DATABASES:
            continue
        reaction = prop == "reacXref"
        obsolete = "secondary/obsolete" in r.get("desc", "")
        xrefs[r["xref"]] = Xref(
            db=DATABASES[prefix],
            id=ident,
            url=r["xref"] if r["xref"].startswith("http") else None,
            name=r.get("src") or (None if obsolete else r.get("desc", "").split("||")[0] or None),
            inchikey=r.get("ik"),
            status=("obsolete" if obsolete else "reaction")
            if reaction
            else xref_status(r.get("ik"), ref_ik, r.get("desc")),
        )
    return list(xrefs.values())


async def fetch_chemical(client: httpx.AsyncClient, mnx_id: str) -> tuple[Chemical, str | None]:
    rows = await sparql(
        client,
        f"""SELECT ?name ?formula ?charge ?mass ?inchikey ?smiles ?refer WHERE {{
          <{CHEM}{mnx_id}> rdfs:comment ?name .
          OPTIONAL {{ <{CHEM}{mnx_id}> mnx:chemRefer/rdfs:label ?refer }}
          OPTIONAL {{ <{CHEM}{mnx_id}> mnx:formula ?formula }} OPTIONAL {{ <{CHEM}{mnx_id}> mnx:charge ?charge }}
          OPTIONAL {{ <{CHEM}{mnx_id}> mnx:mass ?mass }} OPTIONAL {{ <{CHEM}{mnx_id}> mnx:inchikey ?inchikey }}
          OPTIONAL {{ <{CHEM}{mnx_id}> mnx:smiles ?smiles }}
        }} LIMIT 1""",
    )
    if not rows:
        raise ToolError(f"MetaNetX chemical {mnx_id} not found")
    r = rows[0]
    return Chemical(
        id=mnx_id,
        name=r["name"],
        formula=r.get("formula"),
        charge=to_int(r.get("charge")),
        mass=float(r["mass"]) if r.get("mass") else None,
        inchikey=r.get("inchikey"),
        smiles=r.get("smiles"),
        image=image_url(mnx_id, r.get("smiles")),
    ), r.get("refer")


async def fetch_isomers(client: httpx.AsyncClient, mnx_id: str) -> list[Isomer]:
    rows = await sparql(
        client,
        f"""SELECT ?relation ?chem ?name WHERE {{
          {{ <{CHEM}{mnx_id}> mnx:chemIsom ?chem BIND("child" AS ?relation) }}
          UNION {{ ?chem mnx:chemIsom <{CHEM}{mnx_id}> BIND("parent" AS ?relation) }}
          ?chem rdfs:comment ?name .
        }} LIMIT 100""",
    )
    return [Isomer(id=local(r["chem"]), name=r["name"], relation=r["relation"]) for r in rows]


async def fetch_chemical_reactions(client: httpx.AsyncClient, mnx_id: str) -> tuple[list[ReactionRow], int]:
    """Reactions of a chemical in the most models, and the number of its reactions"""
    top, total = await asyncio.gather(
        sparql(
            client,
            f"""SELECT ?reac (COUNT(DISTINCT ?mnet) AS ?n) WHERE {{
              ?p mnx:chem <{CHEM}{mnx_id}> . ?reac mnx:left|mnx:right ?p ; mnx:reacInMNXref true .
              ?mreac mnx:mnxr ?reac . ?gpr mnx:reac ?mreac . ?mnet mnx:gpr ?gpr
            }} GROUP BY ?reac ORDER BY DESC(?n) LIMIT {MAX_REACTIONS}""",
        ),
        sparql(
            client,
            f"""SELECT (COUNT(DISTINCT ?reac) AS ?n) WHERE {{
              ?p mnx:chem <{CHEM}{mnx_id}> . ?reac mnx:left|mnx:right ?p ; mnx:reacInMNXref true }}""",
        ),
    )
    if not top:
        return [], to_int(total[0]["n"]) or 0 if total else 0
    models = {local(r["reac"]): to_int(r["n"]) or 0 for r in top}
    values = " ".join(f"<{REAC}{r}>" for r in models)
    rows = await sparql(
        client,
        f"""SELECT ?reac ?side ?coef ?name ?ec (GROUP_CONCAT(DISTINCT ?rhea; separator=" ") AS ?rheas) WHERE {{
          VALUES ?reac {{ {values} }}
          ?reac ?side ?part . FILTER(?side IN (mnx:left, mnx:right))
          ?part mnx:chem/rdfs:comment ?name ; mnx:coef ?coef .
          OPTIONAL {{ ?reac mnx:classification ?ec }}
          OPTIONAL {{ ?reac mnx:reacXref ?x . FILTER(STRSTARTS(STR(?x), "http://rdf.rhea-db.org/"))
            BIND(STRAFTER(STR(?x), "rhea-db.org/") AS ?rhea) }}
        }} GROUP BY ?reac ?side ?coef ?name ?ec""",
    )
    sides: dict[str, dict[str, list[str]]] = {r: {"left": [], "right": []} for r in models}
    ecs: dict[str, list[str]] = {}
    rheas: dict[str, list[str]] = {}
    for r in rows:
        reac = local(r["reac"])
        coef = r["coef"].removesuffix(".0")
        sides[reac][local(r["side"])].append(f"{'' if coef == '1' else coef + ' '}{r['name']}")
        ecs[reac] = [e for e in r.get("ec", "").split(";") if e]
        rheas[reac] = sorted(set(rheas.get(reac, []) + r.get("rheas", "").split()))
    reactions = [
        ReactionRow(
            id=reac,
            equation=f"{' + '.join(s['left'])} = {' + '.join(s['right'])}",
            ec=ecs.get(reac, []),
            rhea=rheas.get(reac, []),
            models=models[reac],
        )
        for reac, s in sides.items()
    ]
    return reactions, to_int(total[0]["n"]) or 0


async def fetch_reaction(client: httpx.AsyncClient, mnx_id: str) -> dict[str, Any]:
    iri = f"{REAC}{mnx_id}"
    props, participants, models, enzymes = await asyncio.gather(
        sparql(
            client,
            f"""SELECT ?eq ?ec ?balanced ?transport ?refer WHERE {{
              <{iri}> rdfs:comment ?eq .
              OPTIONAL {{ <{iri}> mnx:reacRefer/rdfs:label ?refer }} OPTIONAL {{ <{iri}> mnx:classification ?ec }}
              OPTIONAL {{ <{iri}> mnx:isBalanced ?balanced }} OPTIONAL {{ <{iri}> mnx:isTransport ?transport }}
            }} LIMIT 1""",
        ),
        sparql(
            client,
            f"""SELECT ?side ?coef ?chem ?name ?formula ?charge ?mass ?inchikey ?smiles ?comp ?compName WHERE {{
              <{iri}> ?side ?part . FILTER(?side IN (mnx:left, mnx:right))
              ?part mnx:chem ?chem ; mnx:comp ?comp ; mnx:coef ?coef .
              ?chem rdfs:comment ?name . OPTIONAL {{ ?comp rdfs:comment ?compName }}
              OPTIONAL {{ ?chem mnx:formula ?formula }} OPTIONAL {{ ?chem mnx:charge ?charge }}
              OPTIONAL {{ ?chem mnx:mass ?mass }} OPTIONAL {{ ?chem mnx:inchikey ?inchikey }}
              OPTIONAL {{ ?chem mnx:smiles ?smiles }}
            }}""",
        ),
        sparql(
            client,
            f"""SELECT ?mnet ?organism ?taxid (SAMPLE(?label) AS ?reac) WHERE {{
              ?mreac mnx:mnxr <{iri}> . ?gpr mnx:reac ?mreac . ?mnet mnx:gpr ?gpr .
              OPTIONAL {{ ?gpr rdfs:label ?label }} OPTIONAL {{ ?mnet mnx:organism ?organism }}
              OPTIONAL {{ ?mnet mnx:taxid ?taxid }}
            }} GROUP BY ?mnet ?organism ?taxid""",
        ),
        sparql(
            client,
            f"""SELECT ?mnet (GROUP_CONCAT(DISTINCT STRAFTER(STR(?pxref), "uniprot/"); separator=" ") AS ?uniprot)
            WHERE {{
              ?mreac mnx:mnxr <{iri}> . ?gpr mnx:reac ?mreac ; mnx:cata ?cata . ?mnet mnx:gpr ?gpr .
              ?cata mnx:pept/mnx:peptXref ?pxref FILTER(STRSTARTS(STR(?pxref), "http://purl.uniprot.org/uniprot/"))
            }} GROUP BY ?mnet""",
        ),
    )
    if not props:
        raise ToolError(f"MetaNetX reaction {mnx_id} not found")
    by_model = {r["mnet"]: r["uniprot"].split() for r in enzymes}
    return {
        "props": props[0],
        "participants": [
            Participant(
                id=local(r["chem"]),
                name=r["name"],
                formula=r.get("formula"),
                charge=to_int(r.get("charge")),
                mass=float(r["mass"]) if r.get("mass") else None,
                inchikey=r.get("inchikey"),
                smiles=r.get("smiles"),
                image=image_url(local(r["chem"]), r.get("smiles")),
                side=local(r["side"]),
                coef=float(r["coef"]),
                compartment=local(r["comp"]),
                compartmentName=r.get("compName"),
            )
            for r in sorted(participants, key=lambda r: r["side"])
        ],
        "models": sorted(
            [
                Model(
                    id=local(r["mnet"]),
                    organism=r.get("organism"),
                    taxId=local(r["taxid"]) if r.get("taxid") else None,
                    reaction=r.get("reac"),
                    enzymes=by_model.get(r["mnet"], []),
                )
                for r in models
            ],
            key=lambda m: m["id"].lower(),
        ),
    }


def xrefs_text(xrefs: list[Xref]) -> str:
    by_db: dict[str, list[str]] = {}
    for x in xrefs:
        if x["status"] != "obsolete":
            by_db.setdefault(x["db"], []).append(
                x["id"] + ("" if x["status"] in ("identical structure", "reaction") else f" ({x['status']})")
            )
    return "\n".join(f"- {db}: {', '.join(ids[:12])}{' ...' if len(ids) > 12 else ''}" for db, ids in by_db.items())


@apps.tool(resource_uri="ui://metanetx/metanetx.html", annotations=READ_ONLY)
async def show_metanetx(query: str) -> CallToolResult:
    """Show a chemical or a reaction of MetaNetX (MNXref namespace reconciling metabolic databases) to the user:
    a graph of its identifiers in ChEBI, KEGG, BiGG, SEED, MetaCyc, Rhea, HMDB, LIPID MAPS, SwissLipids, Reactome,
    VMH... with how each one is reconciled (same structure, other protonation or stereo, obsolete). Chemicals also show
    their structure, properties, isomers and the reactions in the most models; reactions their participants with
    compartments, EC numbers and the genome-scale metabolic models (GSMN) containing them with their enzymes.
    `query` is a MetaNetX ID (e.g. MNXM3, MNXR101040), an external identifier (e.g. chebi:15422,
    kegg.compound:C00002, bigg.reaction:LDH_L, rhea:23444) or a chemical name (e.g. glucose 6-phosphate)"""
    async with http_client() as client:
        mnx_id, others = await resolve(client, query)
        if mnx_id.startswith("MNXM"):
            (chemical, reference), isomers, (reactions, total) = await asyncio.gather(
                fetch_chemical(client, mnx_id),
                fetch_isomers(client, mnx_id),
                fetch_chemical_reactions(client, mnx_id),
            )
            xrefs = await fetch_xrefs(client, f"{CHEM}{mnx_id}", "chemXref", chemical["inchikey"])
            data = MetaNetXData(
                kind="chemical",
                id=mnx_id,
                name=chemical["name"],
                reference=reference,
                xrefs=xrefs,
                chemical=chemical,
                isomers=isomers,
                reactions=reactions,
                reactionTotal=total,
                participants=[],
                ec=[],
                balanced=None,
                transport=None,
                models=[],
            )
        else:
            r, xrefs = await asyncio.gather(
                fetch_reaction(client, mnx_id), fetch_xrefs(client, f"{REAC}{mnx_id}", "reacXref", None)
            )
            props = r["props"]
            names: dict[str, str] = {p["id"]: p["name"] for p in r["participants"]}
            # Equation with names, the MNXref one has IDs, e.g. 1 MNXM10@MNXD1 + 1 MNXM1@MNXD1 = ...
            equation = re.sub(r"(MNXM\d+|WATER)@\w+", lambda m: names.get(m[1], m[1]), props["eq"])
            equation = re.sub(r"(^|\+ |= )1 ", r"\1", equation)
            data = MetaNetXData(
                kind="reaction",
                id=mnx_id,
                name=equation,
                reference=props.get("refer"),
                xrefs=xrefs,
                chemical=None,
                isomers=[],
                reactions=[],
                reactionTotal=0,
                participants=r["participants"],
                ec=[e for e in props.get("ec", "").split(";") if e],
                balanced=props["balanced"] in ("1", "true") if "balanced" in props else None,
                transport=props["transport"] in ("1", "true") if "transport" in props else None,
                models=r["models"],
            )

    # Summary for the model
    lines = []
    if data["kind"] == "chemical" and data["chemical"]:
        c = data["chemical"]
        lines.append(
            f"Shown to the user: MetaNetX chemical {mnx_id} {c['name']} (formula {c['formula']}, charge {c['charge']}, "
            f"mass {c['mass']}, InChIKey {c['inchikey']}, reference {data['reference']})\nSMILES: {c['smiles']}"
        )
        if isomers:
            lines.append("Isomers: " + "; ".join(f"{i['relation']} {i['id']} {i['name']}" for i in isomers[:20]))
        lines.append(f"{total} reactions, in the most models:")
        lines += [
            f"- {x['id']} {x['equation']} (EC {', '.join(x['ec'][:5]) or 'none'}; Rhea {', '.join(x['rhea']) or 'none'}; "
            f"{x['models']} models)"
            for x in reactions[:20]
        ]
    else:
        lines.append(
            f"Shown to the user: MetaNetX reaction {mnx_id}: {data['name']} (reference {data['reference']}, "
            f"EC {', '.join(data['ec']) or 'none'}, balanced {data['balanced']}, transport {data['transport']})"
        )
        lines.append(
            "Participants: "
            + "; ".join(
                f"{p['side']} {p['coef']:g} {p['id']} {p['name']} in {p['compartment']}" for p in data["participants"]
            )
        )
        models = data["models"]
        lines.append(
            f"In {len(models)} models: "
            + "; ".join(
                f"{m['id']} ({m['organism']}, {m['reaction']}, enzymes {' '.join(m['enzymes'][:5]) or 'none'})"
                for m in models[:40]
            )
        )
    lines.append(f"Identifiers in other databases:\n{xrefs_text(data['xrefs'])}")
    if others:
        lines.append(f"Other chemicals matching the name, not shown: {'; '.join(others)}")
    lines.append(
        "The user can explore the identifiers graph and click identifiers, reactions or models to ask about them."
    )
    return text_result("\n".join(lines), data)


apps.add_html_resource(
    "ui://metanetx/metanetx.html",
    widget_html("metanetx.html"),
    title="MetaNetX chemical or reaction",
    csp=ResourceCsp(resource_domains=[CDN, MNX_WEB]),
)
