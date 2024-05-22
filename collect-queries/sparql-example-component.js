function searchForExample(text){
  let q=`PREFIX+sh:+<http://www.w3.org/ns/shacl#> PREFIX+schema:+<http://schema.org/> PREFIX+rdfs:+<http://www.w3.org/2000/01/rdf-schema#>+SELECT+?query+?comment+?sparql+(GROUP_CONCAT(?keyword;+separator=",")+AS+?keywords)+WHERE+{
    +?query+a+sh:SPARQLExecutable+;+rdfs:label|rdfs:comment+?comment+;+sh:select|sh:ask|sh:construct|sh:describe+?sparql+.+BIND(IF(REGEX(?comment,+'${text}','i'),1,0)+AS+?matchesComment)+BIND(IF(REGEX(?sparql,+'${text}',+'i'),1,0)+AS+?matchesSparql)+FILTER(?matchesComment+>+0+||+?matchesSparql+>+0)+.+OPTIONAL+{+schema:keyword+?keyword+.}}
    +GROUP+BY+?query+?comment+?sparql+?matchesComment+?matchesSparql+ORDER+BY+DESC(?matchesComment)+DESC(?matchesSparql)+?query+LIMIT+10`

    fetch(`/sparql/?format=json&query=${q}`)
      .then(response => response.json())
      .then(json => json.results.bindings.forEach(b => {
        let li=document.createElement('li');
        let useQuery=document.createElement('button');
        useQuery.class='exampleLink';
        useQuery.innerText='Use';
        li.insertAdjacentHTML("beforeend", b.comment.value);
        li.insertAdjacentElement(useQuery);
      }))
}
