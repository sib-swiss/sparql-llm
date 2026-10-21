// Buttons opening another viewer: they send a prompt as a user message, and the model calls the matching tool
/* eslint-disable no-unused-vars -- globals used by the widget pages, after colors.js */

/** e.g. "BRAF (P15056)" */
const proteinLabel = (p) => (p.gene ? `${p.gene} (${p.accession})` : p.accession);
/** e.g. "residue 600" or "residues 457-717" */
const residuesLabel = ({ start, end }) => (start === end ? `residue ${start}` : `residues ${start}-${end}`);

/** Viewers of one protein, focused on a region of its sequence when given */
const PROTEIN_VIEWERS = {
  features: [
    "Sequence features",
    (p, r) => `Show the sequence features of ${proteinLabel(p)}${r ? `, zoomed on ${residuesLabel(r)}` : ""}`,
  ],
  variants: [
    "Variants",
    (p, r) => `Show the variants of ${proteinLabel(p)}${r ? `, zoomed on ${residuesLabel(r)}` : ""}`,
  ],
  structure: [
    "3D structure",
    (p, r) => `Show the 3D structure of ${proteinLabel(p)}${r ? `, highlighting ${residuesLabel(r)}` : ""}`,
  ],
};

/** Viewers of a list of proteins of one organism */
const LIST_VIEWERS = {
  matrix: [
    "Annotation heatmap",
    (genes, organism) => `Compare the functions of ${genes.join(", ")} (${organism}) in an annotation heatmap`,
  ],
  network: [
    "Interaction network",
    (genes, organism) => `Show how ${genes.join(", ")} (${organism}) are connected in an interaction network`,
  ],
};

/** Button sending its prompt to the conversation, clicks handled by each widget on `[data-prompt]` */
const promptButton = (label, prompt) =>
  `<button type="button" data-prompt="${escapeHtml(prompt)}" title="${escapeHtml(prompt)}">${escapeHtml(label)}</button>`;

/** Buttons opening the viewers of a protein, except the `current` one */
const proteinButtons = (p, region, current) =>
  Object.entries(PROTEIN_VIEWERS)
    .filter(([name]) => name !== current)
    .map(([, [label, prompt]]) => promptButton(label, prompt(p, region)))
    .join("");

/** Buttons opening the viewers of a gene list, except the `current` one */
const listButtons = (genes, organism, current) =>
  Object.entries(LIST_VIEWERS)
    .filter(([name]) => name !== current)
    .map(([, [label, prompt]]) => promptButton(label, prompt(genes, organism)))
    .join("");

/** Button opening the table of the reviewed entries of an organism with a GO term, keyword or Reactome pathway */
const termTableButton = (term, organismId) => {
  const field = term.id.startsWith("GO:")
    ? `go:${term.id.slice(3)}`
    : term.id.startsWith("KW-")
      ? `keyword:${term.id}`
      : `xref:reactome-${term.id}`;
  const query = `${field} AND organism_id:${organismId} AND reviewed:true`;
  return promptButton("All proteins with it", `Search UniProtKB for \`${query}\` (${term.name}) in a table`);
};
