"""The agent as a LangGraph state graph.

  START -> agent --(model asked for a tool)--> tools -> agent
                 --(model gave the answer)---> END

agent: calls the model with the ontology and the conversation so far.
tools: runs the requested tool (run_sql or search_documents) and adds the result to the conversation.

Print the diagram:  python -m agent.graph
"""
import operator
import os
import re
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from agent import usage
from agent.agent import (
    LLM_MODEL,
    MAX_STEPS,
    SYSTEM,
    TOOLS,
    _bedrock,
    dispatch,
    ontology_text,
)
from agent.ontology_lookup import sensitive_columns

GUARDRAIL = (
    {"guardrailIdentifier": os.environ["GUARDRAIL_ID"], "guardrailVersion": os.environ.get("GUARDRAIL_VERSION", "DRAFT")}
    if os.environ.get("GUARDRAIL_ID")
    else None
)
BLOCKED = "I can only answer questions about the Stride Footwear supply chain data."

SYSTEM_PROMPT = [{"text": SYSTEM.format(ontology=ontology_text())}]  # built once, not per step


class AgentState(TypedDict, total=False):
    messages: Annotated[list, operator.add]  # each node appends to the conversation
    trace: Annotated[list, operator.add]     # every tool call, for audit and evals
    steps: int
    answer: str


def agent_node(state):
    steps = state.get("steps", 0) + 1
    if steps > MAX_STEPS:
        return {"steps": steps, "answer": "Stopped: step limit reached."}

    resp = _bedrock.converse(
        modelId=LLM_MODEL,
        system=SYSTEM_PROMPT,
        messages=state["messages"],
        toolConfig={"tools": TOOLS},
        inferenceConfig={"maxTokens": 1500, "temperature": 0},
        **({"guardrailConfig": GUARDRAIL} if GUARDRAIL else {}),
    )
    usage.record(resp)
    if resp["stopReason"] == "guardrail_intervened":
        return {"steps": steps, "answer": BLOCKED}
    msg = resp["output"]["message"]
    update = {"steps": steps, "messages": [msg]}
    if resp["stopReason"] != "tool_use":
        update["answer"] = "".join(block["text"] for block in msg["content"] if "text" in block)
    return update


def tools_node(state):
    last = state["messages"][-1]
    results, trace = [], []
    for block in last["content"]:
        if "toolUse" in block:
            call = block["toolUse"]
            output = dispatch(call["name"], call["input"])
            trace.append({"tool": call["name"], "input": call["input"], "output": output})
            results.append({"toolResult": {"toolUseId": call["toolUseId"], "content": [{"json": output}]}})
    return {"messages": [{"role": "user", "content": results}], "trace": trace}


def route_after_agent(state):
    return END if state.get("answer") else "tools"


builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", tools_node)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")
graph = builder.compile()


def sensitive_notice(trace):
    """A notice to show above the answer when a tool query used a column tagged sensitive in the ontology."""
    tags = sensitive_columns()
    used = {}
    for step in trace:
        if step["tool"] != "run_sql":
            continue
        output = step["output"]
        sql = str(output.get("sql", ""))
        returned = set()
        for row in output.get("rows", []):
            returned.update(row.keys())  # catches SELECT * as well as named columns
        for column, tag in tags.items():
            named = re.search(rf"\b{re.escape(column)}\b", sql, re.IGNORECASE)
            if named or column in returned:
                used[column] = tag
    if not used:
        return ""
    lines = [f"> **Sensitive ({tag}):** this answer uses `{column}`." for column, tag in sorted(used.items())]
    return "\n".join(lines) + "\n\n"


def ask(question):
    final = graph.invoke({
        "messages": [{"role": "user", "content": [{"text": question}]}],
        "trace": [],
        "steps": 0,
    })
    return {"answer": sensitive_notice(final["trace"]) + final["answer"], "trace": final["trace"]}


if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
