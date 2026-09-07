#!/usr/bin/env python3
"""
DockDesk Accuracy Benchmark
============================
Runs DockDesk against the golden-set test fixtures in `fixtures/`
and validates detection accuracy, specifically broken down by file size
to measure the impact of chunking on large files.
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
                          provider: str = "ollama",
                          skip_rag: bool = True) -> list:
    """Run DockDesk audit on a fixture directory and return results."""
    from dockdesk.graph import create_audit_graph
    from dockdesk.config import build_config

    cli_args = {
        "workspace": str(fixture_dir),
        "model": model,
        "provider": provider,
        "reasoning_model": reasoning_model,
        "skip_rag": skip_rag,
        "ci_mode": True,
        "fast_mode": False,
        "verbose": False,
        "force_full_scan": True,  # Benchmark always audits ALL fixture files
        "clear_cache": True,
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

def evaluate_results(results: list, fixtures: list, verbose: bool = False):
    scores = {
        "overall": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
        "small": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
        "large": {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    }

    result_map = {os.path.basename(r.get("file", "")): r for r in results}

    for fix in fixtures:
        fname = fix["file"]
        expected = fix["expected_status"]
        is_large = fix["is_large"]
        bucket = "large" if is_large else "small"

        res = result_map.get(fname)
        if not res:
            if verbose:
                print(f"  [MISSING] {fname} was not audited.")
            if expected == "FAIL":
                scores["overall"]["fn"] += 1
                scores[bucket]["fn"] += 1
            else:
                # If expected PASS and it wasn't audited, technically it's a pass?
                # Actually it's an error in testing, but let's count as fn for safety or ignore
                pass
            continue

        status = res.get("status", "UNKNOWN")
        if verbose:
            print(f"  [{fname}] expected={expected}, got={status}")

        if expected == "FAIL":
            if status == "FAIL":
                scores["overall"]["tp"] += 1
                scores[bucket]["tp"] += 1
            else:
                scores["overall"]["fn"] += 1
                scores[bucket]["fn"] += 1
        elif expected == "PASS":
            if status in ("PASS", "SKIP"):
                scores["overall"]["tn"] += 1
                scores[bucket]["tn"] += 1
            else:
                scores["overall"]["fp"] += 1
                scores[bucket]["fp"] += 1

    return scores

def calc_metrics(bucket_scores):
    tp = bucket_scores["tp"]
    tn = bucket_scores["tn"]
    fp = bucket_scores["fp"]
    fn = bucket_scores["fn"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1

def main():
    parser = argparse.ArgumentParser(description="DockDesk Accuracy Benchmark")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Code analysis model")
    parser.add_argument("--provider", default="ollama", help="LLM Provider")
    parser.add_argument("--reasoning-model", default="deepseek-r1:1.5b", help="Reasoning model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed results")
    parser.add_argument("--skip-tests", action="store_true", help="Skip actually running audit (for dry runs)")
    args = parser.parse_args()

    benchmark_dir = Path(__file__).parent
    fixtures_dir = benchmark_dir / "fixtures"
    manifest_path = fixtures_dir / "fixtures.json"

    with open(manifest_path, "r") as f:
        fixtures = json.load(f)

    print("=" * 60)
    print("DockDesk Accuracy Benchmark (AST-Aware Chunking)")
    print("=" * 60)
    print(f"Fixture dir:      {fixtures_dir}")
    print(f"Total fixtures:   {len(fixtures)}")
    print(f"Code model:       {args.model}")

    if args.skip_tests:
        print("[*] Skipping tests (--skip-tests)")
        sys.exit(0)

    start = time.time()
    try:
        results = run_audit_on_fixture(
            str(fixtures_dir), 
            model=args.model,
            reasoning_model=args.reasoning_model,
            provider=args.provider
        )
    except Exception as e:
        print(f"[-] Audit failed: {e}")
        sys.exit(2)
    elapsed = time.time() - start
    print(f"[+] Audit completed in {elapsed:.1f}s ({len(results)} results)")
    print()

    scores = evaluate_results(results, fixtures, verbose=args.verbose)

    for bucket in ["overall", "small", "large"]:
        p, r, f1 = calc_metrics(scores[bucket])
        print(f"--- {bucket.upper()} FILES ---")
        print(f"  TP: {scores[bucket]['tp']}, TN: {scores[bucket]['tn']}, FP: {scores[bucket]['fp']}, FN: {scores[bucket]['fn']}")
        print(f"  Precision: {p:.2%} | Recall: {r:.2%} | F1: {f1:.2%}\n")

    # Save results
    report = {
        "model": args.model,
        "scores": scores,
        "elapsed_seconds": round(elapsed, 1),
    }
    report_path = benchmark_dir / "benchmark_results.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
if __name__ == "__main__":
    main()
