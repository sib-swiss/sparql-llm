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
  // console.log({endpointUrl, lastQuery});
  // return {endpointUrl, lastQuery};
  return `https://sib-swiss.github.io/sparql-editor/?endpoint=${endpointUrl}&query=${encodeURIComponent(lastQuery)}`;
  // return <a
  //   class="my-3 px-3 py-1 text-sm text-black dark:text-white bg-gray-300 hover:bg-gray-400 dark:bg-gray-700 dark:hover:bg-gray-800 rounded-lg"
  //   href="https://sib-swiss.github.io/sparql-editor/?endpoint=${endpointUrl}&query=${encodeURIComponent(lastQuery)}"
  //   target="_blank"
  // >
  //   Run and edit the query
  // </a>
}

export function getLangForDocType(docType: string) {
  switch (docType) {
    case "sparql_query":
      return "language-sparql";
    case "schemaorg_jsonld":
      return "language-json";
    case "shex":
      return "language-turtle";
    case "ontology":
      return "language-turtle";
    default:
      return "";
  }
}
