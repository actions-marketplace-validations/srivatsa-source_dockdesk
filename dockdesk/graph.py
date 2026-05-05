from langgraph.graph import StateGraph, END
from .state import AuditState
from .nodes import (
    discover_node,
    integrity_node,
    retrieval_node,
    code_analysis_node,
    reasoning_node,
    accountability_node,
    reporting_node,
    notify_node
)

def create_audit_graph():
    workflow = StateGraph(AuditState)
    
    # Add Nodes - Dual-Model Architecture + Accountability
    workflow.add_node("discover", discover_node)
    workflow.add_node("integrity", integrity_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("code_analysis", code_analysis_node)     # Qwen Coder (the "hands")
    workflow.add_node("reasoning", reasoning_node)               # DeepSeek-R1 (the "brain")
    workflow.add_node("accountability", accountability_node)     # Git blame + drift scores
    workflow.add_node("report", reporting_node)
    workflow.add_node("notify", notify_node)                     # Discord webhook
    
    # Define Edges - Linear pipeline with accountability step
    workflow.set_entry_point("discover")
    workflow.add_edge("discover", "integrity")
    workflow.add_edge("integrity", "retrieval")
    workflow.add_edge("retrieval", "code_analysis")
    workflow.add_edge("code_analysis", "reasoning")
    workflow.add_edge("reasoning", "accountability")
    workflow.add_edge("accountability", "report")
    workflow.add_edge("report", "notify")
    workflow.add_edge("notify", END)
    
    return workflow.compile()
