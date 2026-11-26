"""Log each eval run to SageMaker Experiments.

Each pipeline run becomes one run in the experiment "provenance-agent-evals".
Open SageMaker in the AWS console (or Studio) → Experiments to compare runs and scores over time.
"""
import os
from datetime import UTC, datetime

from sagemaker.core.experiments import Run

EXPERIMENT = "provenance-agent-evals"


def log_run(params, metrics):
    commit = os.environ.get("GITHUB_SHA", "local")[:8]
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    with Run(experiment_name=EXPERIMENT, run_name=f"eval-{commit}-{stamp}") as run:
        for name, value in params.items():
            run.log_parameter(name=name, value=str(value))
        for name, value in metrics.items():
            run.log_metric(name=name, value=float(value))
    return f"{EXPERIMENT}/eval-{commit}-{stamp}"
