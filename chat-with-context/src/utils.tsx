export const queryLinkLabels = {
  label: "Run and edit the query",
  title: "Open the SPARQL query in an editor in a new tab",
};

export function extractSparqlQuery(markdownContent: string) {
  // Regular expression to match SPARQL queries within code blocks
  const queryRegex = /```sparql([\s\S]*?)```/g;
  const queries = [...markdownContent.matchAll(queryRegex)].map(match => match[1].trim());

  // Get the last SPARQL query
  const lastQuery = queries.length > 0 ? queries[queries.length - 1] : null;
  if (!lastQuery) return null;

  const endpointRegex = /#.*(https?:\/\/[^\s]+)/i;
  const endpointMatch = lastQuery.match(endpointRegex);
  const endpointUrl = endpointMatch ? endpointMatch[1] : null;
  if (!endpointUrl) return null;
  return getEditorUrl(lastQuery, endpointUrl);
  // return <a
  //   class="my-3 px-3 py-1 text-sm text-black dark:text-white bg-gray-300 hover:bg-gray-400 dark:bg-gray-700 dark:hover:bg-gray-800 rounded-lg"
  //   href="https://sib-swiss.github.io/sparql-editor/?endpoint=${endpointUrl}&query=${encodeURIComponent(lastQuery)}"
  //   target="_blank"
  // >
  //   Run and edit the query
  // </a>
}

export function getEditorUrl(query: string, endpointUrl: string = "") {
  return `https://sib-swiss.github.io/sparql-editor/?${endpointUrl ? `endpoint=${endpointUrl}&` : ""}query=${encodeURIComponent(query)}`;
}

// export function getLangForDocType(docType: string) {
//   switch (docType) {
//     case "SPARQL endpoints query examples":
//       return "language-sparql";
//     // case "General information":
//     //   return "language-json";
//     case "SPARQL endpoints classes schema":
//       return "language-turtle";
//     case "Ontology":
//       return "language-turtle";
//     default:
//       return "";
//   }
// }

// Get filters for color hex here: https://codepen.io/sosuke/pen/Pjoqqp
export const style = `chat-with-context {
  button:hover {
    filter: brightness(90%);
  }
}
.iconBtn {
  filter: invert(44%) sepia(22%) saturate(496%) hue-rotate(176deg) brightness(93%) contrast(79%);
}`;

// @keyframes spin {
//   to {
//     transform: rotate(360deg);
//   }
// }
