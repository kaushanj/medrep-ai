"""Shared backend defaults."""

# SAM cannot import this module. Keep BedrockGenerationModelId Default in
# infra/api-template.yaml (and the ingest SAM template) set to the same value.
DEFAULT_GENERATION_MODEL_ID = "amazon.nova-lite-v1:0"
