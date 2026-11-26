"""Dynamic agent. No question templates: the model reads the ontology, writes its own SQL,
searches the documents, and answers with sources. It touches data only through the tools below."""
import os

from rdflib import OWL, RDF, RDFS, Namespace

from agent.athena import run_query
from agent.aws import session
from agent.ontology_lookup import graph
from agent.rag import search_documents
from agent.sql_guard import UnsafeSQL, check

PROV = Namespace("http://provenance.example/ontology#")
LLM_MODEL = os.environ.get("LLM_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
MAX_STEPS = 8

_bedrock = session().client("bedrock-runtime")


def _name(node):
    return str(node).split("#")[-1]


def _parts(*pairs):
    return "; ".join(f"{label}={value}" for label, value in pairs if value)


def ontology_text():
    """Describe every concept, relationship and rule in the ontology, read from the graph."""
    lines = ["## Concepts and business rules"]
    for cls in sorted(graph.subjects(RDF.type, OWL.Class), key=str):
        lines.append(f"- {_name(cls)}: " + _parts(
            ("labels", ", ".join(str(o) for o in graph.objects(cls, RDFS.label))),
            ("meaning", graph.value(cls, RDFS.comment)),
            ("table", graph.value(cls, PROV.mappedTable)),
            ("key", graph.value(cls, PROV.key)),
            ("rule", graph.value(cls, PROV.sqlCondition)),
            ("threshold", graph.value(cls, PROV.minLateShipments)),
        ))
    lines.append("## Relationships (joins)")
    for prop in sorted(graph.subjects(RDF.type, OWL.ObjectProperty), key=str):
        lines.append(f"- {_name(prop)}: " + _parts(
            ("labels", ", ".join(str(o) for o in graph.objects(prop, RDFS.label))),
            ("join", graph.value(prop, PROV.joinOn)),
        ))
    lines.append("## Column definitions and sensitivity")
    for prop in sorted(graph.subjects(RDF.type, RDF.Property), key=str):
        lines.append(f"- {_name(prop)}: " + _parts(
            ("meaning", graph.value(prop, RDFS.comment)),
            ("column", graph.value(prop, PROV.column)),
            ("sensitivity", graph.value(prop, PROV.sensitivity)),
        ))
    return "\n".join(lines)


SYSTEM = """You answer questions about the Stride Footwear supply chain.

Rules:
1. The ontology below defines every business term. Apply its rule exactly. For example, "delayed" means delivered_date > promised_date, never ship_date.
2. For numbers and lists, write one read-only SELECT with run_sql. Table names are provenance.<table>. Use the joins in the ontology.
3. For contract terms, penalties, delay notices, quality reports and stock notes, call search_documents. Cite the document name for every document fact.
4. If a column is marked sensitive, say which sensitivity applies in your answer.
5. If the data and documents do not answer the question, say so. Do not guess.
6. Keep the answer short. End with the sources used.

# Ontology
{ontology}
"""

TOOLS = [
    {
        "toolSpec": {
            "name": "run_sql",
            "description": "Run one read-only SELECT on the Athena database 'provenance'. Returns up to 50 rows, or an error you can fix and retry.",
            "inputSchema": {"json": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}},
        }
    },
    {
        "toolSpec": {
            "name": "search_documents",
            "description": "Search supplier contracts, delay notices, quality reports, stock notes and the logistics SLA. Returns matching passages with the document name.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
                    "required": ["query"],
                }
            },
        }
    },
]


def dispatch(name, args):
    try:
        if name == "run_sql":
            sql = check(args["sql"])
            rows = run_query(sql)
            return {"sql": sql, "row_count": len(rows), "rows": rows[:50]}
        if name == "search_documents":
            return {"matches": search_documents(args["query"], int(args.get("k", 5)))}
        return {"error": f"unknown tool {name}"}
    except UnsafeSQL as e:
        return {"error": f"rejected: {e}"}
    except Exception as e:  # noqa: BLE001 - the model sees the error and can retry
        return {"error": str(e)}
