/*
Language: Turtle
Author: Mark Ellis <mark.ellis@stardog.com>, Vladimir Alexiev <vladimir.alexiev@ontotext.com>
Category: common
Description: Terse RDF Triple Language for the semantic web
Website: https://www.w3.org/TR/turtle/

Language: SPARQL
Requires: turtle.js
Author: Mark Ellis <mark.ellis@stardog.com>, Vladimir Alexiev <vladimir.alexiev@ontotext.com>
Category: common
Description: SPARQL Protocol and RDF Query Language for the semantic web
Website: https://www.w3.org/TR/sparql11-query/, http://www.w3.org/TR/sparql11-update/, https://www.w3.org/TR/sparql11-federated-query/, http://rawgit2.com/VladimirAlexiev/grammar-diagrams/master/sparql-grammar.xhtml

It's quite horrible highlighting https://github.com/highlightjs/highlightjs-turtle Variables are same colors as prefixed URIs...
There is also https://github.com/redmer/highlightjs-sparql but it is even worse because it imports a ttl language that does not exist, hats off
*/

export function hljsDefineTurtle(hljs: any) {
  var KEYWORDS = {
    keyword: "base|10 prefix|10 @base|10 @prefix|10",
    literal: "true|0 false|0",
    built_in: "a|0",
  };

  var IRI_LITERAL = {
    // https://www.w3.org/TR/turtle/#grammar-production-IRIREF
    className: "literal",
    relevance: 1, // XML tags look also like relative IRIs
    begin: /</,
    end: />/,
    // eslint-disable-next-line no-control-regex
    illegal: /[^\x00-\x20<>"{}|^`]/, // TODO: https://www.w3.org/TR/turtle/#grammar-production-UCHAR
  };

  // https://www.w3.org/TR/turtle/#terminals
  var PN_CHARS_BASE =
    "A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u10000-\uEFFFF";
  var PN_CHARS_U = PN_CHARS_BASE + "_";
  var PN_CHARS = "-" + PN_CHARS_U + "0-9\u00B7\u0300-\u036F\u203F-\u2040";
  var BLANK_NODE_LABEL = "_:[" + PN_CHARS_U + "0-9]([" + PN_CHARS + ".]*[" + PN_CHARS + "])?";
  var PN_PREFIX = "[" + PN_CHARS_BASE + "]([" + PN_CHARS + ".]*[" + PN_CHARS + "])?";
  var PERCENT = "%[0-9A-Fa-f][0-9A-Fa-f]";
  var PN_LOCAL_ESC = "\\\\[_~.!$&'()*+,;=/?#@%-]";
  var PLX = PERCENT + "|" + PN_LOCAL_ESC;
  var PNAME_NS = "(" + PN_PREFIX + ")?:";
  var PN_LOCAL =
    "([" + PN_CHARS_U + ":0-9]|" + PLX + ")([" + PN_CHARS + ".:]|" + PLX + ")*([" + PN_CHARS + ":]|" + PLX + ")?";
  var PNAME_LN = PNAME_NS + PN_LOCAL;
  var PNAME_NS_or_LN = PNAME_NS + "(" + PN_LOCAL + ")?";

  var PNAME = {
    begin: PNAME_NS_or_LN,
    relevance: 0,
    className: "symbol",
  };

  var BLANK_NODE = {
    begin: BLANK_NODE_LABEL,
    relevance: 10,
    className: "template-variable",
  };

  var LANGTAG = {
    begin: /@[a-zA-Z]+([a-zA-Z0-9-]+)*/,
    className: "type",
    relevance: 5, // also catches objectivec keywords like: @protocol, @optional
  };

  var DATATYPE = {
    begin: "\\^\\^" + PNAME_LN,
    className: "type",
    relevance: 10,
  };

  var TRIPLE_APOS_STRING = {
    begin: /'''/,
    end: /'''/,
    className: "string",
    relevance: 0,
  };

  var TRIPLE_QUOTE_STRING = {
    begin: /"""/,
    end: /"""/,
    className: "string",
    relevance: 0,
  };

  var APOS_STRING_LITERAL = JSON.parse(JSON.stringify(hljs.APOS_STRING_MODE));
  APOS_STRING_LITERAL.relevance = 0;

  var QUOTE_STRING_LITERAL = JSON.parse(JSON.stringify(hljs.QUOTE_STRING_MODE));
  QUOTE_STRING_LITERAL.relevance = 0;

  var NUMBER = JSON.parse(JSON.stringify(hljs.C_NUMBER_MODE));
  NUMBER.relevance = 0;

  return {
    case_insensitive: true,
    keywords: KEYWORDS,
    aliases: ["turtle", "ttl", "n3", "ntriples", "shex", "trig"],
    contains: [
      LANGTAG,
      DATATYPE,
      IRI_LITERAL,
      BLANK_NODE,
      PNAME,
      TRIPLE_APOS_STRING,
      TRIPLE_QUOTE_STRING, // order matters
      APOS_STRING_LITERAL,
      QUOTE_STRING_LITERAL,
      NUMBER,
      hljs.HASH_COMMENT_MODE,
    ],
    exports: {
      LANGTAG: LANGTAG,
      DATATYPE: DATATYPE,
      IRI_LITERAL: IRI_LITERAL,
      BLANK_NODE: BLANK_NODE,
      PNAME: PNAME,
      TRIPLE_APOS_STRING: TRIPLE_APOS_STRING,
      TRIPLE_QUOTE_STRING: TRIPLE_QUOTE_STRING,
      APOS_STRING_LITERAL: APOS_STRING_LITERAL,
      QUOTE_STRING_LITERAL: QUOTE_STRING_LITERAL,
      NUMBER: NUMBER,
      KEYWORDS: KEYWORDS,
    },
  };
}

export function hljsDefineSparql(hljs: any) {
  var ttl = hljs.getLanguage("ttl").exports;
  var KEYWORDS = {
    keyword:
      "base|10 prefix|10 @base|10 @prefix|10 add all as|0 ask bind by|0 clear construct|10 copymove create data default define delete describe distinct drop exists filter from|0 graph|10 group having in|0 insert limit load minus named|10 not offset optional order reduced select|0 service silent to union using values where with|0",
    function:
      "abs asc avg bound ceil coalesce concat containsstrbefore count dayhours desc encode_for_uri floor group_concat if|0 iri isblank isiri isliteral isnumeric isuri langdatatype langmatches lcase max md5 min|0 minutes month now rand regex replace round sameterm sample seconds separator sha1 sha256 sha384 sha512 str strafter strdt strends strlang strlen strstarts struuid substr sum then timezone tz ucase uribnode uuid year",
    literal: "true|0 false|0",
    built_in: "a|0",
  };

  var VARIABLE = {
    className: "variable",
    begin: "[?$]" + hljs.IDENT_RE,
    relevance: 0,
  };

  var JSON_QUOTE_STRING = {
    begin: /"""\s*\{/, // TODO why can't I write (?=\{)
    end: /"""/,
    subLanguage: "json",
    excludeBegin: true,
    excludeEnd: true,
    relevance: 0,
  };

  var JSON_APOS_STRING = {
    begin: /'''\s*\{/, // TODO why can't I write (?=\{)
    end: /'''/,
    subLanguage: "json",
    excludeBegin: true,
    excludeEnd: true,
    relevance: 0,
  };

  return {
    case_insensitive: true,
    keywords: KEYWORDS,
    aliases: ["sparql", "rql", "rq", "ru"],
    contains: [
      ttl.LANGTAG,
      ttl.DATATYPE,
      ttl.IRI_LITERAL,
      ttl.BLANK_NODE,
      ttl.PNAME,
      VARIABLE,
      JSON_QUOTE_STRING, // order matters
      JSON_APOS_STRING,
      ttl.TRIPLE_QUOTE_STRING,
      ttl.TRIPLE_APOS_STRING,
      ttl.QUOTE_STRING_LITERAL,
      ttl.APOS_STRING_LITERAL,
      ttl.NUMBER,
      hljs.HASH_COMMENT_MODE,
    ],
  };
}

// window.hljsDefineSparql = hljsDefineSparql;
