from langgraph.graph import StateGraph, END
from .state import AuditState
from .nodes import (
    discover_node,
    integrity_node,
    retrieval_node,
    audit_node,
    reporting_node
)

def create_audit_graph():
    workflow = StateGraph(AuditState)
    
    # Add Nodes
    workflow.add_node("discover", discover_node)
    workflow.add_node("integrity", integrity_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("audit", audit_node)
    workflow.add_node("report", reporting_node)
    
    # Define Edges
    workflow.set_entry_point("discover")
    workflow.add_edge("discover", "integrity")
    
    # Conditional logic could be here, but we'll linearize for now with internal checks
    workflow.add_edge("integrity", "retrieval")
    workflow.add_edge("retrieval", "audit")
    workflow.add_edge("audit", "report")
    workflow.add_edge("report", END)
    
    return workflow.compile()
