"""Run the agent on the golden dataset, grade each answer with G-Eval, log the run to SageMaker,
and fail the pipeline if the score is below the baseline.

Usage (from the project root, with AWS access):
  python -m evals.build_golden
  python -m evals.run_evals
"""
import csv
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from deepeval.test_case import LLMTestCase

from agent.agent import LLM_MODEL
from agent.graph import ask
from evals.judge import JUDGE_MODEL_ID, metrics
from evals.tracking import log_run

HERE = Path(__file__).parent
DATASET = HERE / "golden_dataset.csv"
RESULTS = HERE / "results.json"
BASELINE = float(os.environ.get("EVAL_BASELINE", "0.7"))

# Keep the log readable: only warnings from the AWS and judge libraries
for name in ("botocore", "boto3", "urllib3", "deepeval"):
    logging.getLogger(name).setLevel(logging.WARNING)
DOCUMENT_CATEGORIES = ("document", "hybrid")


def main():
    with DATASET.open() as f:
        cases = list(csv.DictReader(f))
    has_kb = bool(os.environ.get("KNOWLEDGE_BASE_ID"))

    judges = metrics()
    results, skipped = [], 0
    passes = defaultdict(list)          # metric label -> [1 or 0, ...]
    by_category = defaultdict(list)     # category -> [1 or 0, ...] for correctness

    total = len(cases)
    for number, case in enumerate(cases, start=1):
        if case["category"] in DOCUMENT_CATEGORIES and not has_kb:
            skipped += 1
            continue

        try:
            out = ask(case["question"])
        except Exception as e:  # noqa: BLE001 - a failed call is a failed case, not a crashed run
            out = {"answer": f"ERROR: {e}", "trace": []}
        test_case = LLMTestCase(
            input=case["question"],
            actual_output=out["answer"],
            expected_output=case["expected_answer"],
        )

        row = {
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "expected_answer": case["expected_answer"],
            "answer": out["answer"],
            "tools": [step["tool"] for step in out["trace"]],
            "scores": {},
        }
        for label, metric in judges.items():
            try:
                metric.measure(test_case)
                ok = metric.is_successful()
                row["scores"][label] = {"score": metric.score, "passed": ok, "reason": metric.reason}
            except Exception as e:  # noqa: BLE001 - a judge error counts as a failed case
                ok = False
                row["scores"][label] = {"score": 0.0, "passed": False, "reason": f"judge error: {e}"}
            passes[label].append(int(ok))
        by_category[case["category"]].append(int(row["scores"]["correctness"]["passed"]))
        results.append(row)
        status = "PASS" if row["scores"]["correctness"]["passed"] else "FAIL"
        print(f"[{number}/{total}] {status}  [{case['category']}] {case['question']}", flush=True)

    summary = {label: sum(v) / len(v) for label, v in passes.items() if v}
    category_rates = {cat: sum(v) / len(v) for cat, v in by_category.items() if v}

    print("\nPass rate by metric:")
    for label, rate in summary.items():
        print(f"  {label}: {rate:.0%}")
    print("Correctness by category:")
    for cat, rate in sorted(category_rates.items()):
        print(f"  {cat}: {rate:.0%}")
    print(f"Skipped (no knowledge base): {skipped}")

    RESULTS.write_text(json.dumps({"summary": summary, "by_category": category_rates, "cases": results},
                                  indent=2, default=str))

    run_id = log_run(
        params={
            "agent_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL_ID,
            "cases_run": len(results),
            "cases_skipped": skipped,
            "baseline": BASELINE,
        },
        metrics={**{f"pass_rate_{k}": v for k, v in summary.items()},
                 **{f"correctness_{k}": v for k, v in category_rates.items()}},
    )
    print(f"Logged to SageMaker Experiments: {run_id}")

    failing = {label: rate for label, rate in summary.items() if rate < BASELINE}
    if failing or not summary:
        for label, rate in failing.items():
            print(f"FAILED: {label} is {rate:.0%}, below the required {BASELINE:.0%}")
        if not summary:
            print("FAILED: no cases were scored")
        sys.exit(1)
    print(f"PASSED: every metric meets the required {BASELINE:.0%}")


if __name__ == "__main__":
    main()
