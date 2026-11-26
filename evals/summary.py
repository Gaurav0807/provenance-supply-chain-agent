"""Write the eval results as a Markdown table for the GitHub run summary.

Usage in CI:  python -m evals.summary >> "$GITHUB_STEP_SUMMARY"
"""
import json
from pathlib import Path

RESULTS = Path(__file__).parent / "results.json"


def main():
    if not RESULTS.exists():
        print("## Eval results\n\nNo results file was written. The run stopped before scoring.")
        return
    data = json.loads(RESULTS.read_text())
    lines = ["## Eval results", "", "| Metric | Pass rate |", "|---|---|"]
    lines += [f"| {name} | {rate:.0%} |" for name, rate in data["summary"].items()]
    lines += ["", "### By category", "", "| Category | Correctness |", "|---|---|"]
    lines += [f"| {cat} | {rate:.0%} |" for cat, rate in data["by_category"].items()]
    lines += ["", "### Cases", "", "| ID | Category | Result | Question |", "|---|---|---|---|"]
    for case in data["cases"]:
        result = "PASS" if case["scores"]["correctness"]["passed"] else "FAIL"
        lines.append(f"| {case['id']} | {case['category']} | {result} | {case['question']} |")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
