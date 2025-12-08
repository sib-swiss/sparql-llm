# Text2SPARQL Benchmark

Follow these steps to run the benchmark:

## 1. Download the [data dumps](https://text2sparql.aksw.org/challenge/#knowledge-graphs-for-evaluation)

**DBpedia files:**  
- `dbpedia_2015-10.nt`
- `instance_types_en.nt`
- `labels_en.nt`
- `mappingbased_objects_en.nt`
- `short_abstracts_en.nt`
- `infobox_properties_en.nt`
- `instance_types_transitive_en.nt`
- `mappingbased_literals_en.nt`
- `persondata_en.nt`

**Corporate files:**  
- `prod-inst.ttl`
- `prod-vocab.ttl`

Store the downloaded files in the following directory structure:

```
data/benchmarks/Text2SPARQL/dumps/<dataset>/
```

> **Note:** Replace `<dataset>` with either `dbpedia` or `corporate`

## 2. Set Up Virtuoso and TEXT2SPARQL API Using Docker

Use the provided docker compose file:

```bash
docker compose -f compose.text2sparql.yml up -d
```

## 3. Store the Data

Run the following script:

```bash
tests/text2sparql/data_store.sh
```

> **Note:** If the files are not stored properly in the dockerized Virtuoso instance, consider loading them into a native Virtuoso installation first, and then moving the resulting `virtuoso.db` file into `data/benchmarks/Text2SPARQL/virtuosodb/`.

## 4. Sanity Check

After storing the data, the following query at `http://localhost:8890/sparql` should return these results:

```sparql
SELECT ?g (COUNT(*) AS ?triples) WHERE { 
    VALUES ?g { 
        <https://text2sparql.aksw.org/2025/dbpedia/> 
        <https://text2sparql.aksw.org/2025/corporate/> 
    } 
    GRAPH ?g {
        ?s ?p ?o
    } 
}
```

| g                                            | triples    |
|----------------------------------------------|------------|
| https://text2sparql.aksw.org/2025/dbpedia/   | 171560889  |
| https://text2sparql.aksw.org/2025/corporate/ | 26903      |

## 5. Download Queries

Download the following files and store them in `data/benchmarks/Text2SPARQL/queries/`:

- [Text2SPARQL](https://github.com/AKSW/text2sparql.aksw.org/blob/develop/docs/benchmark/questions_db25.yaml)
- [QALD-9+](https://github.com/Perevalov/QALD_9_plus/tree/main/data) (train and test DBpedia files)
- [LC-QuAD v1](https://github.com/AskNowQA/LC-QuAD/tree/data) (train and test files)

## 6. Transform Queries

```bash
uv run tests/text2sparql/query_transform.py
```
> **Note:** This will create a `queries.csv` file

## 7. Analyze Queries

```bash
uv run tests/text2sparql/query_analysis.py
```

## 8. Index Queries

```bash
uv run tests/text2sparql/index.py
```

## 9. Run TEXT2SPARQL Benchmark

```bash
uv run tests/text2sparql/evaluate.sh [db|ck]
```
> **Note:** Use *db* for the *DBpedia* subtask and *ck* for the *Corporate* subtask of the TEXT2SPARQL benchmark

## 10. Plot Final Results
```bash
uv run tests/text2sparql/experiments_results.py 
```
