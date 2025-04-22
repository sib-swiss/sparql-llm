export const queryLinkLabels = {
  label: "Run or edit the query",
  title: "Open the SPARQL query in an editor in a new tab",
};

export function getEditorUrl(query: string, endpointUrl: string = "") {
  return `https://sib-swiss.github.io/sparql-editor/?${endpointUrl ? `endpoint=${endpointUrl}&` : ""}query=${encodeURIComponent(query)}`;
}

// Get filters for color hex here: https://codepen.io/sosuke/pen/Pjoqqp
export const style = `chat-with-context {
  button:hover {
    filter: brightness(90%);
  }
}
.iconBtn {
  filter: invert(44%) sepia(22%) saturate(496%) hue-rotate(176deg) brightness(93%) contrast(79%);
}`;

// // A function to extract a SPARQL query from markdown text
// export function extractSparqlQuery(markdownContent: string) {
//   // Regular expression to match SPARQL queries within code blocks
//   const queryRegex = /```sparql([\s\S]*?)```/g;
//   const queries = [...markdownContent.matchAll(queryRegex)].map(match => match[1].trim());

//   // Get the last SPARQL query
//   const lastQuery = queries.length > 0 ? queries[queries.length - 1] : null;
//   if (!lastQuery) return null;

//   const endpointRegex = /#.*(https?:\/\/[^\s]+)/i;
//   const endpointMatch = lastQuery.match(endpointRegex);
//   const endpointUrl = endpointMatch ? endpointMatch[1] : null;
//   if (!endpointUrl) return null;
//   return getEditorUrl(lastQuery, endpointUrl);
// }
