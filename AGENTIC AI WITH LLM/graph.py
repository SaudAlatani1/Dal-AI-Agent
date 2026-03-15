"""
graph.py — Simplified 2-node LangGraph pipeline.
START → logic_node → formatter_node → END
"""

from typing import Any, TypedDict

from langgraph.graph import StateGraph, END  # type: ignore[import-untyped]
from nodes import logic_node, formatter_node  # type: ignore[import-untyped]


class AgentState(TypedDict):
    user_input: str
    rewritten_query: str
    category: str
    validated_platforms: list[dict[str, Any]]
    final_response: str


def build_graph() -> Any:
    workflow = StateGraph(AgentState)

    workflow.add_node("logic", logic_node)
    workflow.add_node("formatter", formatter_node)

    workflow.set_entry_point("logic")
    workflow.add_edge("logic", "formatter")
    workflow.add_edge("formatter", END)

    return workflow.compile()
