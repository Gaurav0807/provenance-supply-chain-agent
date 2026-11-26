"""G-Eval judge. DeepEval's GEval metrics, with Claude Haiku on Bedrock as the judge model.

The judge is Haiku and the agent is Sonnet, so the agent never grades its own answers.
"""
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # no data sent to DeepEval's servers

from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import SingleTurnParams

from agent.aws import session

JUDGE_MODEL_ID = os.environ.get("JUDGE_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
_bedrock = session().client("bedrock-runtime")


class BedrockJudge(DeepEvalBaseLLM):
    """Lets DeepEval call Claude Haiku through Bedrock."""

    def __init__(self, model_id=JUDGE_MODEL_ID):
        self.model_id = model_id

    def load_model(self):
        return self

    def generate(self, prompt, schema=None):
        resp = _bedrock.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1000, "temperature": 0},
        )
        return resp["output"]["message"]["content"][0]["text"]

    async def a_generate(self, prompt, schema=None):
        return self.generate(prompt, schema)

    def get_model_name(self):
        return self.model_id


def metrics():
    """The G-Eval metrics, keyed by a short label used in reports."""
    judge = BedrockJudge()
    return {
        "correctness": GEval(
            name="Correctness",
            criteria=(
                "Does the actual output state the same facts as the expected output? "
                "The same names or IDs, the same numbers (within 1% for money), and the same conclusion. "
                "Missing or wrong facts fail. Extra correct detail is fine. Saying the data does not say fails."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            threshold=0.7,
            async_mode=False,
        ),
        "source_citation": GEval(
            name="Source citation",
            criteria=(
                "If the expected output comes from a contract, delay notice, quality report, stock note "
                "or SLA, the actual output must name the source document. If the expected output does not "
                "come from a document, pass."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            threshold=0.7,
            async_mode=False,
        ),
    }
