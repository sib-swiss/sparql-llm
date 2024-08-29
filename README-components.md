# 🦜✨ LangChain SPARQL

Utilities to improve LLMs capabilities when working with SPARQL endpoints. In particular improving SPARQL query generation.

Loaders are compatible with LangChain, but they can also be used outside of LangChain as they just return a list of documents with metadata as JSON, which can then be loaded how you want in your vectorstore.

## Features

### SPARQL query examples loader

Load SPARQL query examples defined using the SHACL ontology from a SPARQL endpoint. See [github.com/sib-swiss/sparql-examples](https://github.com/sib-swiss/sparql-examples) for more details on how to define the examples.

```python
from langchain_sparql import SparqlExamplesLoader

loader = SparqlExamplesLoader("https://sparql.uniprot.org/sparql/")
docs = loader.load()
print(len(docs))
print(docs[0].metadata)
```

### SPARQL endpoint ShEx shapes from VoID description loader

Load ShEx shapes describing all classes of a SPARQL endpoint based on the VoID description present in your endpoint. Ideally the endpoint should also contain the ontology describing the class, so the `rdfs:label` and `rdfs:comment` of the class can be used to generate embeddings and improve semantic matching.

Checkout the **[void-generator](https://github.com/JervenBolleman/void-generator)** project to automatically generate VoID description for your endpoint.

```python
from langchain_sparql import SparqlVoidShapesLoader

loader = SparqlVoidShapesLoader("https://sparql.uniprot.org/sparql/")
docs = loader.load()
print(len(docs))
print(docs[0].metadata)
```

### Generate complete ShEx shapes from VoID description

You can also generate the complete ShEx shapes for a SPARQL endpoint with:

```python
from langchain_sparql import get_shex_from_void

shex_str = get_shex_from_void("https://sparql.uniprot.org/sparql/")
```

