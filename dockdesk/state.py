from typing import TypedDict, List, Dict, Optional, Any
from dataclasses import dataclass

class AuditState(TypedDict):
    # Inputs
    workspace_path: str
    
    # Configuration
    config: Optional[Any]  # DockDeskConfig instance
    model: str                    # Code analysis model (Qwen Coder)
    reasoning_model: str          # Logical reasoning model (DeepSeek-R1)
    model_tier: str
    total_loc: int
    
    # Internal State
    discovered_files: List[str]
    changed_files: List[str]
    file_contents: Dict[str, str]
    file_hashes: Dict[str, str]
    doc_sources: List[Dict]  # serialized DocumentationSource
    
    context_data: str  # RAG retrieved context
    
    # Dual-model pipeline intermediate state
    code_findings: List[Dict]     # Raw findings from Qwen Coder (Phase 1)
    audit_results: List[Dict]     # Final results after DeepSeek reasoning (Phase 2)
    fix_results: Optional[List[Any]]  # FixResult instances
    
    # Metadata
    run_id: str                   # Unique identifier for this execution
    
    # Outputs
    report_path: str
    mermaid_graph: str
    
    # Metadata
    run_metadata: Optional[Dict]
    
    # Orchestration and metrics
    orchestration_metrics: Optional[Dict[str, Any]]
