// https://sparql.uniprot.org/sparql.js
// Note that we add `&ac=1` to all the queries for the prefixes to exclude these queries from stats
// Code for UniProt SPARQL examples https://sparql.uniprot.org/.well-known/sparql-examples

class Sparql {

	constructor(yasge) {
		this.prefixes = new Map([['up', 'http://purl.uniprot.org/core/'],
						['keywords', 'http://purl.uniprot.org/keywords/'],
						['uniprotkb', 'http://purl.uniprot.org/uniprot/'],
						['taxon', 'http://purl.uniprot.org/taxonomy/'],
						['ec', 'http://purl.uniprot.org/enzyme/'],
						['rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'],
						['rdfs', 'http://www.w3.org/2000/01/rdf-schema#'],
						['skos', 'http://www.w3.org/2004/02/skos/core#'],
						['owl', 'http://www.w3.org/2002/07/owl#'],
						['bibo', 'http://purl.org/ontology/bibo/'],
						['dc', 'http://purl.org/dc/terms/'],
						['xsd', 'http://www.w3.org/2001/XMLSchema#'],
						['faldo', 'http://biohackathon.org/resource/faldo#']]);
		fetch('/sparql/?format=json&ac=1&query=PREFIX sh:<http://www.w3.org/ns/shacl%23> SELECT ?prefix ?namespace WHERE { [] sh:namespace ?namespace ; sh:prefix ?prefix} ORDER BY ?prefix')
			.then(response => response.json())
			.then(json => json.results.bindings.forEach(b => {
				this.prefixes.set(b.prefix.value, b.namespace.value);
				let pref = {};
				pref[b.prefix.value] = b.namespace.value;
				yasge.addPrefixes(pref);
			}
			))
			.then((x) => yasge.collapsePrefixes(true));
	}
	addCommonPrefixes(yasge) {
		const prefixLink = document.getElementById('addPrefix');
		const prefixesCapture = this.prefixes;
		if (prefixLink !== null) {
			prefixLink.addEventListener('click', function() {
				const sortedKeys = [...prefixesCapture.keys()].sort();
				for (let key of sortedKeys) {
					const value = prefixesCapture.get(key);
					let pref = {};
					pref[key] = value;
					yasge.addPrefixes(pref);
				};
			});
		}
	}
	addCommonPrefixesToQuery(yasqe) {
		const val = yasqe.getValue();
		const sortedKeys = [...this.prefixes.keys()].sort();
		for (let key of sortedKeys) {
			const value = this.prefixes.get(key);
			let pref = {};
			pref[key] = value;
			var prefix = 'PREFIX ' + key + ' ?: ?<' + value;
			if (!new RegExp(prefix, 'g').test(val) && new RegExp('[(| |\u00a0|/]' + key + ':', 'g').test(val)) {
				yasqe.addPrefixes(pref);
			}
		};
	}
}

var uniprot = {};



const myTextArea = document.getElementById('query');
YASQE.defaults.consumeShareLink = null;
YASQE.defaults.sparql.showQueryButton = false;
YASQE.defaults.sparql.consumeShareLink = false;
YASQE.defaults.sparql.createShortLink = false;
YASQE.defaults.autocompleters = ["prefixes", "variables"];
YASQE.Autocompleters.prefixes.fetchFrom = '/prefixes.json'
var voidPredicateCompleter = function(yasqe) {
    // we use several functions from the regular property autocompleter (this
    // way, we don't have to re-define code such as determining whether we are
    // in a valid autocompletion position)
    var returnObj = {
        isValidCompletionPosition: function() { return YASQE.Autocompleters.properties.isValidCompletionPosition(yasqe) },
        preProcessToken: function(token) { return YASQE.Autocompleters.properties.preProcessToken(yasqe, token) },
        postProcessToken: function(token, suggestedString) { return YASQE.Autocompleters.properties.postProcessToken(yasqe, token, suggestedString) }
    };

    // In this case we assume the properties will fit in memory. So, turn on
    // bulk loading, which will make autocompleting a lot faster
    returnObj.bulk = true;
    returnObj.async = true;

    // and, as everything is in memory, enable autoShowing the completions
    returnObj.autoShow = true;

    //	returnObj.persistent = location.hostname;// this will store the sparql
    //												// results in the client-cache
    //												// for a month.
    returnObj.get = function(token, callback) {
        // all we need from these parameters is the last one: the callback to
        // pass the array of completions to

        const sparqlQuery = "PREFIX void: <http://rdfs.org/ns/void#> SELECT DISTINCT ?property { [] void:linkPredicate|void:property ?property } ORDER BY ?property";
        //		 console.log(callback);
        const url = '/sparql/' +
            '?format=csv&ac=1&query=' + encodeURIComponent(sparqlQuery);
        //		 console.log('fetch from', url);

        fetch(url)
            .then((response) => response.text())
            .then(function(text) {
                var data = text.split('\n');
                data.shift();
                return callback(data);
            })
            .catch((error) => { console.error('Error:', error) });
    };
    return returnObj;
};

var voidClassCompleter = function(yasqe) {
    // we use several functions from the regular property autocompleter (this
    // way, we don't have to re-define code such as determining whether we are
    // in a valid autocompletion position)
    var returnObj = {
        isValidCompletionPosition: function() { return YASQE.Autocompleters.classes.isValidCompletionPosition(yasqe) },
        preProcessToken: function(token) { return YASQE.Autocompleters.classes.preProcessToken(yasqe, token) },
        postProcessToken: function(token, suggestedString) {
            for (const [key, value] of Object.entries(yasqe.getPrefixesFromQuery())) {
                if (suggestedString.startsWith(value)) {
                    return key + ":" + suggestedString.substr(value.length);
                }
            };
            return YASQE.Autocompleters.classes.postProcessToken(yasqe, token, suggestedString);
        },

        // In this case we assume the properties will fit in memory. So, turn on
        // bulk loading, which will make autocompleting a lot faster
        bulk: true,
        async: true,

        // and, as everything is in memory, enable autoShowing the completions
        autoShow: true
    };

    //	returnObj.persistent = location.hostname;// this will store the sparql
    //												// results in the client-cache
    //												// for a month.
    returnObj.get = function(token, callback) {
        // all we need from these parameters is the last one: the callback to
        // pass the array of completions to

        const sparqlQuery = "PREFIX void: <http://rdfs.org/ns/void#> SELECT DISTINCT ?class { [] void:class ?class } ORDER BY ?class ";
        //		 console.log(callback);
        const url = '/sparql/' +
            '?format=csv&ac=1&query=' + encodeURIComponent(sparqlQuery);
        //		 console.log('fetch from', url);

        fetch(url)
            .then((response) => response.text())
            .then(function(text) {
                var data = text.split('\n');
                data.shift();
                return callback(data);
            })
            .catch((error) => { console.error('Error:', error) });
    };
    return returnObj;
};
// now register our new autocompleters
YASQE.registerAutocompleter('voidClassCompleter', voidClassCompleter);
YASQE.registerAutocompleter('voidPredicateCompleter', voidPredicateCompleter);

if (myTextArea !== null) {
    const myCodeMirror = YASQE.fromTextArea(myTextArea, { value: myTextArea.value, createShareLink: null });
    uniprot.Sparql = new Sparql(myCodeMirror);
    const lq = new URLSearchParams(location.search).get('lastQuery');
    if (lq !== null) {
        myCodeMirror.setValue(lq);
    }
    document.getElementById('sparqlFormSubmitter').addEventListener('click', function() {
        // UPS-14 In case the JS DOM has not been reset remove the query object
        // now.
        const form = document.getElementById('sparql-form');
       // const textArea = form.getElementsByTagName('textarea');
        //textArea.id = "query";
        //textArea.name = "query";
        //textArea.hidden = true;
        let value = myCodeMirror.getValue();
        let valueLines = value.split('\n');
        for (let pref of uniprot.Sparql.prefixes ){
			let match = value.match(new RegExp('(?:^|[\\s+\/\|\(])'+pref[0]+':', 'g'));
			if (match !== null && match.length === 1){
				let re = "[pP][rR][eE][fF][iI][xX]\\s+" + pref[0]+":\\s*<"+pref[1].replace(/[.*+?^${}()\\/|[\]\\]/g, '\\$&')+">";
				let toRemove= new RegExp(re, "g");
				for (let i = 0; i < valueLines.length; i++) {
					if (valueLines[i] !== null){
						let matchToRemove = valueLines[i].replaceAll(toRemove, "");
						if (matchToRemove.length === 0 && valueLines[i].length !== matchToRemove.length) {
							valueLines[i] = null;
						}
					}
				}
			}
		}
		myCodeMirror.setValue(valueLines.filter(l => l !== null).join('\n'));
		//textArea.value = valueLines.filter(l => l !== null).join('\n');
		if (myCodeMirror.getValue().length > 600) {
            form.method = "POST";
        }
        console.log(myCodeMirror.getValue().value);
        //form.insertAdjacentElement('beforeend', textArea);

        form.submit();

        return false;
    });

    const examples = document.getElementsByClassName('exampleQuery');
    for (let example of examples) {
        const show = document.createElement('button');
        show.className = "exampleLink";
        show.innerHTML = "Use";
        example.parentElement.insertAdjacentElement('beforeend', show);
        example.hidden = true;
        show.addEventListener('click', function(target) {
            const parentofclicked = target.currentTarget.parentElement;
            const clickedexample = parentofclicked.querySelector('.exampleQuery');
            text = clickedexample.textContent;
            myCodeMirror.setValue(text);
            uniprot.Sparql.addCommonPrefixesToQuery(myCodeMirror);
            return false;
        });
        uniprot.Sparql.addCommonPrefixes(myCodeMirror);
    };
    const show = document.getElementById('showSparqlQuery');
    if (show !== null) {
        show.addEventListener('click', function() {
            document.getElementById('queryform').hidden = false;
            Array.from(document.querySelectorAll(".page-title"))
                .forEach(el => {
                    el.hidden = !el.matches('.showQueryTitle');
                });
            myCodeMirror.refresh();
            document.getElementById('resultsArea').hidden = true;
        });
    }
    const hide = document.getElementById('hideSparqlQuery');
    if (hide !== null) {
        hide.addEventListener('click', function() {
            Array.from(document.querySelectorAll(".page-title"))
                .forEach(el => {
                    el.hidden = el.matches('.showQueryTitle');
                });
            document.getElementById('queryform').hidden = true;
            document.getElementById('resultsArea').hidden = false;
        });
    }

}
