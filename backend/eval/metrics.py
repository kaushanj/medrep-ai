"""DeepEval RAG metrics for the offline evaluator (issue #17)."""

from __future__ import annotations

import os
from typing import Any

from utils.constants import DEFAULT_GENERATION_MODEL_ID

DEFAULT_THRESHOLD = 0.5


def build_eval_model() -> Any:
    """Build one shared Bedrock judge model from existing env configuration."""
    from deepeval.models import AmazonBedrockModel

    model_id = (
        os.environ.get("BEDROCK_EVAL_MODEL_ID")
        or os.environ.get("BEDROCK_GENERATION_MODEL_ID")
        or DEFAULT_GENERATION_MODEL_ID
    )
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_BEDROCK_REGION")
        or "us-east-1"
    )
    return AmazonBedrockModel(
        model=model_id,
        region=region,
        generation_kwargs={"temperature": 0},
    )


def _metric_result(metric: Any) -> dict[str, Any]:
    score = getattr(metric, "score", None)
    reason = getattr(metric, "reason", "") or ""
    if callable(getattr(metric, "is_successful", None)):
        passed = bool(metric.is_successful())
    else:
        passed = bool(getattr(metric, "success", False))
    return {
        "score": score,
        "passed": passed,
        "is_successful": passed,
        "reason": reason,
    }


def run_deepeval_metrics(
    question: str,
    answer: str,
    context: str,
    *,
    model: Any | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, dict[str, Any]]:
    """Score Faithfulness, Answer Relevancy, and Contextual Relevancy once.

    Reuses a single LLMTestCase (and shared Bedrock model) so retrieval and
    generation are not repeated for metrics.

    DeepEval is imported lazily so main-deps unit tests can collect without
    installing offline eval requirements.
    """
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    eval_model = model or build_eval_model()
    retrieval_context = [context] if context else []
    test_case = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=retrieval_context,
    )

    faithfulness = FaithfulnessMetric(threshold=threshold, model=eval_model)
    answer_relevancy = AnswerRelevancyMetric(
        threshold=threshold, model=eval_model
    )
    contextual_relevancy = ContextualRelevancyMetric(
        threshold=threshold, model=eval_model
    )

    faithfulness.measure(test_case)
    answer_relevancy.measure(test_case)
    contextual_relevancy.measure(test_case)

    return {
        "faithfulness": _metric_result(faithfulness),
        "answer_relevancy": _metric_result(answer_relevancy),
        "contextual_relevancy": _metric_result(contextual_relevancy),
    }
