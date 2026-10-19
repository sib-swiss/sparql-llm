// Feature colors by type (ProtVista-like), shared by the features and structure widgets
/* eslint-disable no-unused-vars -- globals used by the widget pages */
const FEATURE_COLORS = {
  Domain: "#2e86c1",
  Repeat: "#48c9b0",
  Region: "#a569bd",
  Motif: "#f5b041",
  "Zinc finger": "#873600",
  "DNA binding": "#1abc9c",
  "Coiled coil": "#5d6d7e",
  "Compositional bias": "#95a5a6",
  "Active site": "#e74c3c",
  "Binding site": "#f39c12",
  Site: "#d35400",
  "Modified residue": "#8e44ad",
  Glycosylation: "#27ae60",
  Lipidation: "#16a085",
  "Disulfide bond": "#d4ac0d",
  "Cross-link": "#c0392b",
  Signal: "#e67e22",
  "Transit peptide": "#ca6f1e",
  Propeptide: "#b9770e",
  Chain: "#85929e",
  Peptide: "#5499c7",
  "Initiator methionine": "#7f8c8d",
  "Topological domain": "#aab7b8",
  Transmembrane: "#cb4335",
  Intramembrane: "#e59866",
  Helix: "#e91e63",
  "Beta strand": "#ffc107",
  Turn: "#2196f3",
  "Natural variant": "#c0392b",
  Mutagenesis: "#7d3c98",
};
const featureColor = (f) => FEATURE_COLORS[f.type] ?? "#888888";
const featurePos = (f) => (f.start === f.end ? `${f.start}` : `${f.start}-${f.end}`);
/** Residues displayed to zoom on a region: padded, and at least 30 residues wide to read the sequence */
const regionWindow = ({ start, end }, length) => {
  const width = end - start + 1;
  const pad = Math.max(5, Math.ceil(width * 0.1), Math.ceil((30 - width) / 2));
  return [Math.max(1, start - pad), Math.min(length, end + pad)];
};
/** Short label, e.g. "E17K" or "150-408 Protein kinase" */
const featureLabel = (f) => [f.change ?? featurePos(f), f.description.split(";")[0]].filter(Boolean).join(" ");
/** Evidence URLs by source, persistent ones when the source has them (DOI, PURL, identifiers.org) */
const EVIDENCE_URLS = {
  PubMed: (id) => `https://pubmed.ncbi.nlm.nih.gov/${id}/`,
  PDB: (id) => `https://doi.org/10.2210/pdb${id.toLowerCase()}/pdb`,
  UniProtKB: (id) => `https://purl.uniprot.org/uniprot/${id}`,
  // Citation of the entry, e.g. Ref.37
  Reference: (_id, accession) => `https://www.uniprot.org/uniprotkb/${accession}/publications`,
  "HAMAP-Rule": (id) => `https://hamap.expasy.org/rule/${id}`,
  "PROSITE-ProRule": (id) => `https://prosite.expasy.org/rule/${id}`,
  PROSITE: (id) => `https://prosite.expasy.org/${id}`,
  Pfam: (id) => `https://www.ebi.ac.uk/interpro/entry/pfam/${id}`,
  Ensembl: (id) => `https://identifiers.org/ensembl:${id}`,
  ARBA: (id) => `https://www.uniprot.org/arba/${id}`,
  UniRule: (id) => `https://www.uniprot.org/unirule/${id}`,
  SAM: (id, accession) => (id === "MobiDB-lite" ? `https://mobidb.org/${accession}` : null),
};
/** Evidence link, e.g. PDB:1UNQ, or null for sources without a page */
const refUrl = (ref, accession) => {
  const i = ref.indexOf(":");
  return EVIDENCE_URLS[ref.slice(0, i)]?.(ref.slice(i + 1), accession) ?? null;
};
const escapeHtml = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
