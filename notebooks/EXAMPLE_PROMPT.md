> **System prompt:**
>
> You are Expasy, an assistant that helps users to navigate the resources and databases from the Swiss Institute of Bioinformatics.
>
> Depending on the user request and provided context, you may provide general information about the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
>
> If answering with a query:
>
> Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and indicate the URL of the endpoint on which the query should be executed in a comment at the start of the query (no additional text, just the endpoint URL directly as comment, always and only 1 endpoint).
>
> If answering with a query always derive your answer from the queries and endpoints provided as examples in the prompt, don't try to create a query from nothing and do not provide a generic query.
>
> Try to always answer with one query, if the answer lies in different endpoints, provide a federated query. Do not add more codeblocks than necessary.

Here is a list of reference questions and query answers relevant to the user question that will help you answer the user question accurately:

Find the orthologous proteins for UniProtKB entry P05067 using the OrthoDB database:

```sparql
# https://sparql.uniprot.org/sparql/
PREFIX orthodb: <http://purl.orthodb.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX uniprotkb: <http://purl.uniprot.org/uniprot/>
PREFIX up: <http://purl.uniprot.org/core/>

SELECT
  ?protein
  ?orthoGroup
  ?scientificName
  ?functionComment
  ?prefferedGeneName
  ((STRLEN(?value) - ?medianLength) as ?deviationFromMedianLength)
WHERE
{
  uniprotkb:P05067 a up:Protein ;
        up:organism/up:scientificName ?scientificName ;
        rdfs:seeAlso ?orthoGroup ;
        up:encodedBy/skos:prefLabel ?prefferedGeneName ;
          up:sequence/rdf:value ?value .
  OPTIONAL {
    ?protein up:annotation ?functionAnnotation .
    ?functionAnnotation a up:Function_Annotation ;
      rdfs:comment ?functionComment .
  }
  SERVICE <https://sparql.orthodb.org/sparql>{
    ?orthoGroup orthodb:ogMedianProteinLength ?medianLength .
    ?orthoGroup orthodb:hasMember ?xref .
    ?xref orthodb:xref/orthodb:xrefResource uniprotkb:P05067 .
  }
}
```

Retrieve all genes that are orthologous to ENSLACG00000002497 Ensembl gene (identifier):

```sparql
# https://sparql.omabrowser.org/sparql/
PREFIX sio: <http://semanticscience.org/resource/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX ensembl: <http://rdf.ebi.ac.uk/resource/ensembl/>
select ?protein2 ?OMA_LINK 
where {
    #The three that contains Orthologs. The leafs are proteins.
    #This graph pattern defines the relationship protein1 is Orthologs to protein2
    ?cluster a orth:OrthologsCluster.
    ?cluster orth:hasHomologousMember ?node1.
    ?cluster orth:hasHomologousMember ?node2. 
    ?node2 orth:hasHomologousMember* ?protein2. 
    ?node1 orth:hasHomologousMember* ?protein1.
    ########
     
    #Specify the protein to look for its orthologs
    ?protein1 sio:SIO_010079/lscr:xrefEnsemblGene  ensembl:ENSLACG00000002497.
    ########
     
    #The OMA link to the second protein
    ?protein2 rdfs:seeAlso ?OMA_LINK. 
    ########
     
    filter(?node1 != ?node2) 
}
```

Retrieve all proteins belongong to the Hierarchical Orthologous Group (HOG) at the level 'Vertebrata' to which humans' CDIN1 gene belong, together with their gene name symbol if available.:

```sparql
# https://sparql.omabrowser.org/sparql/
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
select distinct ?HOG ?MEMBER ?GENE_LABEL
where {
    ?HOG a orth:OrthologsCluster ;
      orth:hasHomologousMember ?node1 ;
      orth:hasTaxonomicRange ?taxRange .
    ?taxRange orth:taxRange 'Vertebrata' .
    ?node1 orth:hasHomologousMember* ?query ;
      orth:hasHomologousMember* ?MEMBER .
    ?MEMBER a orth:Protein .
    OPTIONAL {
        ?MEMBER rdfs:label ?GENE_LABEL .
    }
    ?query a orth:Protein ;
      orth:organism/obo:RO_0002162/up:scientificName 'Homo sapiens';
      rdfs:label 'CDIN1'.
}
```

Retrieve all genes that are orthologous to HUMAN22169 OMA protein (identifier) and their cross-reference links to OMA and Uniprot.:

```sparql
# https://sparql.omabrowser.org/sparql/
PREFIX orth: <http://purl.org/net/orth#>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX dc: <http://purl.org/dc/terms/>
select ?protein2 ?Uniprot_link
where {
    ?cluster a orth:OrthologsCluster.
    ?cluster orth:hasHomologousMember ?node1.
    ?cluster orth:hasHomologousMember ?node2.
    ?node2 orth:hasHomologousMember* ?protein2.
    ?node1 orth:hasHomologousMember* ?protein1.
    ?protein1 a orth:Protein.
    ?protein1 dc:identifier 'HUMAN22169'.
    ?protein2 a orth:Protein. 
    ?protein2  lscr:xrefUniprot ?Uniprot_link. 
    filter(?node1 != ?node2)
}
```

Find all Rattus norvegicus' proteins present in OMA RDF database.:

```sparql
# https://sparql.omabrowser.org/sparql/
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
SELECT ?protein ?OMA_link
WHERE
{
    ?protein a orth:Protein.
    ?protein  orth:organism ?organism.
    ?inTaxon rdfs:label 'in taxon'@en.
    ?organism ?inTaxon ?taxon.
    ?taxon  up:scientificName 'Rattus norvegicus'.
    ?protein rdfs:seeAlso ?OMA_link.
}
```

Here is some additional information that could be useful to answer the user question:

ShEx shape for Cluster of orthologs in https://sparql.omabrowser.org/sparql/:
```
orth:OrthologsCluster {
  a [ orth:OrthologsCluster ] ;
  orth:hasTaxonomicRange [ up:Taxon orth:TaxonomicRange ] ;
  orth:hasHomologousMember [ orth:OrthologsCluster orth:ParalogsCluster orth:Protein ] ;
  orth:inDataset [ orth:OrthologyDataset ] ;
  dc:identifier xsd:string
}
```

ShEx shape for Cluster of proteins with similar sequences. in https://sparql.uniprot.org/sparql/:
```
up:Cluster {
  a [ up:Cluster ] ;
  up:member [ up:Sequence ] ;
  up:identity xsd:float ;
  rdfs:label xsd:string ;
  up:modified xsd:date ;
  up:commonTaxon IRI ;
  up:someMembersClassifiedWith IRI
}
```

ShEx shape for Member Of Redudant Proteome in https://sparql.uniprot.org/sparql/:
```
up:Member_Of_Redudant_Proteome {
  a [ up:Member_Of_Redudant_Proteome ] ;
  up:replacedBy [ up:Member_Of_Redudant_Proteome up:Protein ] ;
  up:created xsd:date ;
  up:mnemonic xsd:string ;
  up:modified xsd:date ;
  up:obsolete xsd:boolean ;
  up:reviewed xsd:boolean ;
  up:version xsd:int
}
```

ShEx shape for http://rdf.ebi.ac.uk/resource/ensembl/protein in https://sparql.omabrowser.org/sparql/:
```
ensembl:protein {
  a [ ensembl:protein ] ;
  dc:identifier xsd:string
}
```

The question from the user is:
What are the rat orthologs of the human TP53?
