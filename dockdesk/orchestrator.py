
import time
from typing import Dict, List, Any
from dockdesk.state import AuditState

def execute_analysis(state: AuditState) -> AuditState:
    '''Populate orchestration metrics at current pipeline stage.'''
    start_time = time.time()
    
    files_count = len(state.get('discovered_files', []))
    code_findings_count = len(state.get('code_findings', []))
    audit_results_count = len(state.get('audit_results', []))
    
    risk_distribution = {
        'HIGH': sum(1 for r in state.get('audit_results', []) if r.get('risk') == 'HIGH'),
        'MEDIUM': sum(1 for r in state.get('audit_results', []) if r.get('risk') == 'MEDIUM'),
        'LOW': sum(1 for r in state.get('audit_results', []) if r.get('risk') == 'LOW'),
    }
    
    pass_fail = {
        'PASS': sum(1 for r in state.get('audit_results', []) if r.get('status') == 'PASS'),
        'FAIL': sum(1 for r in state.get('audit_results', []) if r.get('status') == 'FAIL'),
    }
    
    metrics = state.get('orchestration_metrics', {})
    metrics.update({
        'files_discovered': files_count,
        'files_analyzed': code_findings_count,
        'findings_count': audit_results_count,
        'risk_distribution': risk_distribution,
        'pass_fail_distribution': pass_fail,
        'model_used': state.get('model', 'unknown'),
        'reasoning_model_used': state.get('reasoning_model', 'unknown'),
        'total_loc': state.get('total_loc', 0)
    })
    
    state['orchestration_metrics'] = metrics
    return state

