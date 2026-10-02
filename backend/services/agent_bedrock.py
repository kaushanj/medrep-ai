"""Bedrock chat model bound to trusted evidence retrieval tools."""

import os

from langchain_aws import ChatBedrockConverse

from services.agent_tools import (
    search_dailymed_evidence_tool,
    search_internal_documents_tool,
)
from utils.constants import DEFAULT_GENERATION_MODEL_ID


def build_bedrock_model_with_internal_docs_tool():
    """Return a Bedrock chat model with evidence tools bound.

    Does not invoke tools or run an agent loop — bind only.
    """
    model = ChatBedrockConverse(
        model=os.environ.get(
            "BEDROCK_GENERATION_MODEL_ID",
            DEFAULT_GENERATION_MODEL_ID,
        ),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        temperature=0,
    )
    return model.bind_tools(
        [
            search_internal_documents_tool,
            search_dailymed_evidence_tool,
        ]
    )
