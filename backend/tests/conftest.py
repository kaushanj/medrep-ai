"""Shared pytest fixtures for backend API tests."""

import pytest

from api.rate_limit import reset_for_tests


@pytest.fixture(autouse=True)
def _reset_chat_rate_limiter():
    """Keep the in-process rate-limit store isolated between tests."""
    reset_for_tests()
    yield
    reset_for_tests()
