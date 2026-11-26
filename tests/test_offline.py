"""Tests that run without AWS: the ontology text, the eval cases, and the document pages."""
from agent.agent import ontology_text
from agent.ontology_lookup import graph
from evals.make_cases import build_cases


def test_ontology_text_has_the_delay_rule():
    text = ontology_text()
    assert "Delayed" in text
    assert "provenance.shipments.delivered_date > provenance.purchase_orders.promised_date" in text


def test_ontology_loads_all_classes():
    assert len(graph) > 50


def test_eval_cases_cover_all_categories():
    cases = build_cases()
    categories = {c["category"] for c in cases}
    assert categories == {"structured", "document", "hybrid", "refusal"}
    assert len(cases) >= 30



def test_graph_has_agent_and_tools_nodes():
    from agent.graph import graph

    nodes = set(graph.get_graph().nodes)
    assert {"agent", "tools"} <= nodes


def test_route_ends_when_answer_is_present():
    from langgraph.graph import END

    from agent.graph import route_after_agent

    assert route_after_agent({"answer": "done"}) == END
    assert route_after_agent({"messages": []}) == "tools"


def test_sensitive_notice_for_finance_column():
    from agent.graph import sensitive_notice

    trace = [{"tool": "run_sql", "output": {"sql": "SELECT sku, unit_cost FROM provenance.products"}}]
    assert "Sensitive (finance)" in sensitive_notice(trace)
    assert sensitive_notice([{"tool": "run_sql", "output": {"sql": "SELECT model FROM provenance.products"}}]) == ""


def test_sensitive_notice_when_query_uses_star():
    from agent.graph import sensitive_notice

    trace = [{"tool": "run_sql", "output": {
        "sql": "SELECT * FROM provenance.products WHERE sku = 'SF-001'",
        "rows": [{"sku": "SF-001", "unit_cost": "35.26"}],
    }}]
    assert "Sensitive (finance)" in sensitive_notice(trace)


def test_allowed_table_passes():
    from agent.sql_guard import check

    assert check("SELECT * FROM provenance.products").startswith("SELECT * FROM provenance.products")


def test_other_tables_are_refused():
    import pytest

    from agent.sql_guard import UnsafeSQL, check

    for sql in ["SELECT * FROM other_db.secret", "SELECT * FROM information_schema.tables"]:
        with pytest.raises(UnsafeSQL):
            check(sql)
