#!/usr/bin/env python3
"""
DockDesk Accuracy Benchmark
============================
Runs DockDesk against the golden-set test fixtures and validates detection
accuracy. Returns exit 0 if accuracy meets thresholds, exit 1 otherwise.

Usage:
    python tests/benchmark/test_accuracy.py
    python tests/benchmark/test_accuracy.py --verbose
    python tests/benchmark/test_accuracy.py --model qwen2.5-coder:3b

Requirements:
    - Ollama running with default models pulled
    - DockDesk installed (pip install -e .)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_audit_on_fixture(fixture_dir: str, model: str = "qwen2.5-coder:7b",
                          reasoning_model: str = "deepseek-r1:1.5b",
                          skip_rag: bool = True) -> list:
    """Run DockDesk audit on a fixture directory and return results."""
    from dockdesk.graph import create_audit_graph
    from dockdesk.config import build_config

    cli_args = {
        "workspace": str(fixture_dir),
        "model": model,
        "reasoning_model": reasoning_model,
        "skip_rag": skip_rag,
        "ci_mode": True,
        "fast_mode": False,
        "verbose": False,
        "force_full_scan": True,  # Benchmark always audits ALL fixture files
    }
    config = build_config(cli_args, str(fixture_dir))

    app = create_audit_graph()
    initial_state = {
        "workspace_path": str(fixture_dir),
        "discovered_files": [],
        "changed_files": [],
        "file_contents": {},
        "file_hashes": {},
        "doc_sources": [],
        "context_data": "",
        "code_findings": [],
        "audit_results": [],
        "mermaid_graph": "",
        "discord_posted": None,
        "config": config,
        "model": model,
        "reasoning_model": reasoning_model,
        "model_tier": "benchmark",
        "total_loc": 0,
    }

    result = app.invoke(initial_state)
    return result.get("audit_results", [])


def evaluate_vulnerable_app(results: list, verbose: bool = False) -> dict:
    """Check that vulnerable_app.py is flagged with FAIL + HIGH/MEDIUM risk.
    
    Expected detections (ground truth):
      - SQL injection / non-parameterized query
      - Hardcoded secrets / API keys
      - Return type mismatch (dict vs tuple)
      - Missing error handling
      - MD5 instead of bcrypt
      - Missing function parameters
      - Incomplete state coverage
      
    We expect: status=FAIL, risk in (HIGH, MEDIUM), at least 2 findings.
    """
    scores = {"true_positive": 0, "false_negative": 0, "details": []}
    
    vuln_results = [r for r in results 
                    if "vulnerable_app" in str(r.get("file", "")).lower()]
    
    if not vuln_results:
        scores["false_negative"] = 1
        scores["details"].append("MISS: vulnerable_app.py not found in results")
        return scores
    
    for r in vuln_results:
        status = r.get("status", "UNKNOWN")
        risk = r.get("risk", "UNKNOWN")
        findings = r.get("findings", [])
        summary = r.get("summary", "")
        
        if verbose:
            print(f"  [vulnerable_app] status={status} risk={risk} "
                  f"findings={len(findings)} summary={summary[:100]}")
        
        # Ground truth: should be FAIL
        if status == "FAIL":
            scores["true_positive"] += 1
            scores["details"].append(f"DETECT: status=FAIL (correct)")
        else:
            scores["false_negative"] += 1
            scores["details"].append(f"MISS: status={status} (expected FAIL)")
        
        # Ground truth: should be HIGH or MEDIUM risk
        if risk in ("HIGH", "MEDIUM"):
            scores["true_positive"] += 1
            scores["details"].append(f"DETECT: risk={risk} (correct)")
        else:
            scores["false_negative"] += 1
            scores["details"].append(f"MISS: risk={risk} (expected HIGH/MEDIUM)")
        
        # Should have at least 2 findings
        if len(findings) >= 2:
            scores["true_positive"] += 1
            scores["details"].append(f"DETECT: {len(findings)} findings (>=2 expected)")
        elif len(findings) >= 1:
            scores["true_positive"] += 0.5
            scores["details"].append(f"PARTIAL: {len(findings)} finding (>=2 expected)")
        else:
            scores["false_negative"] += 1
            scores["details"].append(f"MISS: 0 findings (>=2 expected)")
        
        # Check for keyword detection in summary/findings
        combined_text = (summary + " " + " ".join(str(f) for f in findings)).lower()
        keywords = ["sql", "inject", "secret", "key", "hardcod", "bcrypt", "md5",
                     "return type", "mismatch", "parameter", "missing"]
        keyword_hits = sum(1 for k in keywords if k in combined_text)
        if keyword_hits >= 2:
            scores["true_positive"] += 1
            scores["details"].append(f"DETECT: {keyword_hits} security keywords found")
        elif keyword_hits >= 1:
            scores["true_positive"] += 0.5
            scores["details"].append(f"PARTIAL: {keyword_hits} security keyword found")
        else:
            scores["false_negative"] += 1
            scores["details"].append(f"MISS: no security keywords in findings")
    
    return scores


def evaluate_clean_app(results: list, verbose: bool = False) -> dict:
    """Check that clean_app.py passes with LOW risk (no false positives).
    
    Expected: status=PASS or SKIP, risk=LOW, 0 findings.
    """
    scores = {"true_negative": 0, "false_positive": 0, "details": []}
    
    clean_results = [r for r in results 
                     if "clean_app" in str(r.get("file", "")).lower()]
    
    if not clean_results:
        # No result means it wasn't flagged — that's correct for a clean file
        scores["true_negative"] += 1
        scores["details"].append("OK: clean_app.py not flagged (correct)")
        return scores
    
    for r in clean_results:
        status = r.get("status", "UNKNOWN")
        risk = r.get("risk", "UNKNOWN")
        findings = r.get("findings", [])
        
        if verbose:
            print(f"  [clean_app] status={status} risk={risk} findings={len(findings)}")
        
        # Ground truth: should be PASS or SKIP
        if status in ("PASS", "SKIP"):
            scores["true_negative"] += 1
            scores["details"].append(f"OK: status={status} (correct)")
        else:
            scores["false_positive"] += 1
            scores["details"].append(f"FALSE_POS: status={status} (expected PASS/SKIP)")
        
        # Ground truth: should be LOW risk
        if risk == "LOW":
            scores["true_negative"] += 1
            scores["details"].append(f"OK: risk=LOW (correct)")
        else:
            scores["false_positive"] += 1
            scores["details"].append(f"FALSE_POS: risk={risk} (expected LOW)")
    
    return scores


def main():
    parser = argparse.ArgumentParser(description="DockDesk Accuracy Benchmark")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Code analysis model")
    parser.add_argument("--reasoning-model", default="deepseek-r1:1.5b", help="Reasoning model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed results")
    parser.add_argument("--min-precision", type=float, default=0.6,
                        help="Minimum precision threshold (default: 0.6)")
    parser.add_argument("--min-recall", type=float, default=0.5,
                        help="Minimum recall threshold (default: 0.5)")
    args = parser.parse_args()

    benchmark_dir = Path(__file__).parent
    
    print("=" * 60)
    print("DockDesk Accuracy Benchmark")
    print("=" * 60)
    print(f"Fixture dir:      {benchmark_dir}")
    print(f"Code model:       {args.model}")
    print(f"Reasoning model:  {args.reasoning_model}")
    print(f"Min precision:    {args.min_precision}")
    print(f"Min recall:       {args.min_recall}")
    print()

    # Run audit
    print("[*] Running audit on benchmark fixtures...")
    start = time.time()
    try:
        results = run_audit_on_fixture(
            benchmark_dir, 
            model=args.model,
            reasoning_model=args.reasoning_model,
        )
    except Exception as e:
        print(f"[-] Audit failed: {e}")
        sys.exit(2)
    elapsed = time.time() - start
    print(f"[+] Audit completed in {elapsed:.1f}s ({len(results)} results)")
    print()

    # Evaluate
    print("[*] Evaluating vulnerable_app.py (should detect issues)...")
    vuln_scores = evaluate_vulnerable_app(results, verbose=args.verbose)
    
    print("[*] Evaluating clean_app.py (should pass cleanly)...")
    clean_scores = evaluate_clean_app(results, verbose=args.verbose)
    print()
    
    # Compute metrics
    tp = vuln_scores["true_positive"]
    fn = vuln_scores["false_negative"]
    tn = clean_scores["true_negative"]
    fp = clean_scores["false_positive"]
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    print("=" * 60)
    print("Results")
    print("=" * 60)
    print(f"  True Positives:  {tp}")
    print(f"  False Negatives: {fn}")
    print(f"  True Negatives:  {tn}")
    print(f"  False Positives: {fp}")
    print(f"  Precision:       {precision:.2%}")
    print(f"  Recall:          {recall:.2%}")
    print(f"  F1 Score:        {f1:.2%}")
    print(f"  Elapsed:         {elapsed:.1f}s")
    print()
    
    if args.verbose:
        print("Detailed breakdown:")
        for d in vuln_scores["details"]:
            print(f"  vuln: {d}")
        for d in clean_scores["details"]:
            print(f"  clean: {d}")
        print()
    
    # Save results
    report = {
        "model": args.model,
        "reasoning_model": args.reasoning_model,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": tp,
        "false_negatives": fn,
        "true_negatives": tn,
        "false_positives": fp,
        "elapsed_seconds": round(elapsed, 1),
        "raw_results": results,
    }
    report_path = benchmark_dir / "benchmark_results.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[+] Report saved: {report_path}")
    
    # Pass/fail
    passed = precision >= args.min_precision and recall >= args.min_recall
    if passed:
        print(f"[PASS] Precision {precision:.2%} >= {args.min_precision:.0%}, "
              f"Recall {recall:.2%} >= {args.min_recall:.0%}")
        sys.exit(0)
    else:
        print(f"[FAIL] Precision {precision:.2%} (need {args.min_precision:.0%}), "
              f"Recall {recall:.2%} (need {args.min_recall:.0%})")
        sys.exit(1)


if __name__ == "__main__":
    main()
