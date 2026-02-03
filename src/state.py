from typing import TypedDict, List, Dict, Optional, Any
from dataclasses import dataclass

class AuditState(TypedDict):
    # Inputs
    workspace_path: str
    
    # Configuration
    config: Optional[Any]  # DockDeskConfig instance
    model: str
    model_tier: str
    total_loc: int
    
    # Internal State
    discovered_files: List[str]
    changed_files: List[str]
    file_contents: Dict[str, str]
    file_hashes: Dict[str, str]
    doc_sources: List[Dict]  # serialized DocumentationSource
    
    context_data: str  # RAG retrieved context
    
    audit_results: List[Dict]
    fix_results: Optional[List[Any]]  # FixResult instances
    
    # Outputs
    report_path: str
    mermaid_graph: str
    
    # Metadata
    run_metadata: Optional[Dict]
