"""Shared backend defaults."""

# SAM cannot import this module. Keep BedrockGenerationModelId Default in
# infra/template.yaml set to the same value.
DEFAULT_GENERATION_MODEL_ID = "amazon.nova-lite-v1:0"
