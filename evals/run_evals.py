"""Run the agent on the golden dataset, grade each answer, log the run and its cost to SageMaker,
and fail the pipeline if any metric is below the baseline.

Metrics per case:
  correctness      G-Eval judge (one judge call per case)
  source_citation  checked in code: document answers must name a document the agent retrieved

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

from agent import usage
from agent.agent import LLM_MODEL
from agent.graph import ask
from evals.judge import JUDGE_MODEL_ID, metrics
from evals.tracking import log_run

HERE = Path(__file__).parent
DATASET = HERE / "golden_dataset.csv"
RESULTS = HERE / "results.json"
BASELINE = float(os.environ.get("EVAL_BASELINE", "0.7"))
DOCUMENT_CATEGORIES = ("document", "hybrid")

# Keep the log readable: only warnings from the AWS and judge libraries
for name in ("botocore", "boto3", "urllib3", "deepeval"):
    logging.getLogger(name).setLevel(logging.WARNING)


def cited_document(answer, trace):
    """True if the answer names a document the agent actually retrieved in this run."""
    names = set()
    for step in trace:
        if step["tool"] == "search_documents":
            for match in step["output"].get("matches", []):
                doc = match["doc"]
                names.update({doc, doc.rsplit(".", 1)[0]})
    lowered = answer.lower()
    return any(name.lower() in lowered for name in names)


def main():
    with DATASET.open() as f:
        cases = list(csv.DictReader(f))
    has_kb = bool(os.environ.get("KNOWLEDGE_BASE_ID"))
    judge = metrics()["correctness"]

    results, skipped = [], 0
    passes = defaultdict(list)        # metric -> [1 or 0, ...]
    by_category = defaultdict(list)   # category -> [1 or 0, ...]
    total = len(cases)

    for number, case in enumerate(cases, start=1):
        if case["category"] in DOCUMENT_CATEGORIES and not has_kb:
            skipped += 1
            continue

        before = usage.snapshot()
        try:
            out = ask(case["question"])
        except Exception as e:  # noqa: BLE001 - a failed call is a failed case, not a crashed run
            out = {"answer": f"ERROR: {e}", "trace": []}

        try:
            judge.measure(LLMTestCase(
                input=case["question"],
                actual_output=out["answer"],
                expected_output=case["expected_answer"],
            ))
            correct, correct_reason, correct_score = judge.is_successful(), judge.reason, judge.score
        except Exception as e:  # noqa: BLE001 - a judge error counts as a failed case
            correct, correct_reason, correct_score = False, f"judge error: {e}", 0.0

        if case["category"] in DOCUMENT_CATEGORIES:
            cited = cited_document(out["answer"], out["trace"])
        else:
            cited = True
        after = usage.snapshot()

        passes["correctness"].append(int(correct))
        passes["source_citation"].append(int(cited))
        by_category[case["category"]].append(int(correct and cited))
        status = "PASS" if correct and cited else "FAIL"
        print(f"[{number}/{total}] {status}  [{case['category']}] {case['question']}", flush=True)

        results.append({
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "expected_answer": case["expected_answer"],
            "answer": out["answer"],
            "tools": [step["tool"] for step in out["trace"]],
            "scores": {
                "correctness": {"score": correct_score, "passed": correct, "reason": correct_reason},
                "source_citation": {"passed": cited},
            },
            "model_calls": after["calls"] - before["calls"],
            "input_tokens": after["input_tokens"] - before["input_tokens"],
            "output_tokens": after["output_tokens"] - before["output_tokens"],
        })

    summary = {label: sum(v) / len(v) for label, v in passes.items() if v}
    category_rates = {cat: sum(v) / len(v) for cat, v in by_category.items() if v}
    cost = usage.snapshot()

    print("\nPass rate by metric:")
    for label, rate in summary.items():
        print(f"  {label}: {rate:.0%}")
    print("Pass rate by category:")
    for cat, rate in sorted(category_rates.items()):
        print(f"  {cat}: {rate:.0%}")
    print(f"Skipped (no knowledge base): {skipped}")
    print(f"Model calls: {cost['calls']}  input tokens: {cost['input_tokens']}  output tokens: {cost['output_tokens']}")

    RESULTS.write_text(json.dumps({"summary": summary, "by_category": category_rates,
                                  "cost": cost, "cases": results}, indent=2, default=str))

    run_id = log_run(
        params={
            "agent_model": LLM_MODEL,
            "judge_model": JUDGE_MODEL_ID,
            "cases_run": len(results),
            "cases_skipped": skipped,
            "baseline": BASELINE,
        },
        metrics={
            **{f"pass_rate_{k}": v for k, v in summary.items()},
            **{f"pass_rate_category_{k}": v for k, v in category_rates.items()},
            "model_calls": cost["calls"],
            "input_tokens": cost["input_tokens"],
            "output_tokens": cost["output_tokens"],
        },
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
