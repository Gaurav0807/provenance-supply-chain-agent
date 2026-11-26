"""The agent as a LangGraph state graph.

  START -> agent --(model asked for a tool)--> tools -> agent
                 --(model gave the answer)---> END

agent: calls the model with the ontology and the conversation so far.
tools: runs the requested tool (run_sql or search_documents) and adds the result to the conversation.

Print the diagram:  python -m agent.graph
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.agent import (
    LLM_MODEL,
    MAX_STEPS,
    SYSTEM,
    TOOLS,
    _bedrock,
    dispatch,
    ontology_text,
)

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
    )
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


def ask(question):
    final = graph.invoke({
        "messages": [{"role": "user", "content": [{"text": question}]}],
        "trace": [],
        "steps": 0,
    })
    return {"answer": final["answer"], "trace": final["trace"]}


if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
