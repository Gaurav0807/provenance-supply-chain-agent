"""Write the golden dataset to evals/golden_dataset.csv.

Runs on every pipeline run, before the evals. Each expected answer is computed from the same
data that is in S3, so the dataset always matches the files. Commit the CSV so the cases can be reviewed.

Usage (from the project root):
  python -m evals.build_golden
"""
import csv
from pathlib import Path

from evals.make_cases import build_cases

OUT = Path(__file__).parent / "golden_dataset.csv"
FIELDS = ["id", "category", "question", "expected_answer"]


def main():
    cases = build_cases()
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, case in enumerate(cases, start=1):
            writer.writerow({
                "id": f"G{i:03d}",
                "category": case["category"],
                "question": case["question"],
                "expected_answer": case["reference"],
            })
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
