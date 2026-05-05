
import time
import uuid
from typing import Dict, List, Any
from dockdesk.state import AuditState


def generate_run_id() -> str:
    """Generate a unique audit run identifier."""
    return f"dd-{uuid.uuid4().hex[:12]}"


def execute_analysis(state: AuditState) -> AuditState:
    """Populate orchestration metrics at the END of the pipeline (post-reasoning).

    This should only be called ONCE, after audit_results are fully populated,
    to avoid producing zeroed-out metrics from premature calls.
    """
    start_time = time.time()

    files_count = len(state.get('discovered_files', []))
    code_findings_count = len(state.get('code_findings', []))
    audit_results = state.get('audit_results', [])
    audit_results_count = len(audit_results)

    risk_distribution = {
        'HIGH': sum(1 for r in audit_results if r.get('risk') == 'HIGH'),
        'MEDIUM': sum(1 for r in audit_results if r.get('risk') == 'MEDIUM'),
        'LOW': sum(1 for r in audit_results if r.get('risk') == 'LOW'),
    }

    pass_fail = {
        'PASS': sum(1 for r in audit_results if r.get('status') == 'PASS'),
        'FAIL': sum(1 for r in audit_results if r.get('status') == 'FAIL'),
        'SKIP': sum(1 for r in audit_results if r.get('status') == 'SKIP'),
        'ERROR': sum(1 for r in audit_results if r.get('status') == 'ERROR'),
    }

    # Per-file model usage tracking
    models_used = {}
    total_duration_ms = 0
    for r in audit_results:
        cm = r.get('code_model', 'unknown')
        models_used[cm] = models_used.get(cm, 0) + 1
        total_duration_ms += r.get('duration_ms', 0)

    avg_duration_ms = total_duration_ms // max(audit_results_count, 1)

    # Safe-to-push summary
    safe_count = sum(1 for r in audit_results if r.get('safe_to_push'))
    unsafe_count = audit_results_count - safe_count

    # Reuse run_id if already present on state, otherwise generate new
    run_id = state.get("run_id")
    if not run_id:
        run_id = generate_run_id()
        state["run_id"] = run_id

    metrics = state.get('orchestration_metrics', {})
    metrics.update({
        'run_id': run_id,
        'files_discovered': files_count,
        'files_analyzed': code_findings_count,
        'findings_count': audit_results_count,
        'risk_distribution': risk_distribution,
        'pass_fail_distribution': pass_fail,
        'model_used': state.get('model', 'unknown'),
        'reasoning_model_used': state.get('reasoning_model', 'unknown'),
        'models_per_file': models_used,
        'total_loc': state.get('total_loc', 0),
        'total_duration_ms': total_duration_ms,
        'avg_duration_ms': avg_duration_ms,
        'safe_to_push': safe_count,
        'unsafe_to_push': unsafe_count,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    })

    state['orchestration_metrics'] = metrics
    return state
