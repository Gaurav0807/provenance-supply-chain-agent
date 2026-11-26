"""Load the ontology and answer lookups: which concept a term means, its rule, its tables and joins."""
import re

import rdflib

graph = rdflib.Graph()
graph.parse("ontology/provenance.ttl", format="turtle")

PREFIXES = """
PREFIX prov: <http://provenance.example/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
"""

join_query = PREFIXES + """
SELECT ?link ?label ?join WHERE {
  ?link a owl:ObjectProperty ;
        rdfs:label ?label ;
        prov:joinOn ?join .
}
"""


def lookup_term(word):
    q = PREFIXES + """
SELECT ?concept ?condition WHERE {
  ?concept rdfs:label ?label ;
           prov:sqlCondition ?condition .
  FILTER (lcase(str(?label)) = \"""" + word.lower().replace('"', "") + """\")
}
"""
    return [(str(r.concept), str(r.condition)) for r in graph.query(q)]


def tables_in(condition):
    return sorted(set(re.findall(r"provenance\.[a-z_]+", condition)))


def joins_for(tables):
    if not tables:
        return []
    return [str(r.join) for r in graph.query(join_query)
            if all(t in str(r.join) for t in tables)]


def get_context(word):
    results = []
    for concept, condition in lookup_term(word):
        tables = tables_in(condition)
        results.append({
            "concept": concept,
            "condition": condition,
            "tables": tables,
            "joins": joins_for(tables),
        })
    return results


if __name__ == "__main__":
    print(len(graph), "facts loaded")
    for word in ["late", "out of stock", "at-risk supplier"]:
        print(word, "->", get_context(word))
