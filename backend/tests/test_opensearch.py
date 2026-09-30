from unittest.mock import MagicMock, patch

import repositories.opensearch as opensearch_repo


def _reset_opensearch_cache():
    opensearch_repo._client = None


def test_opensearch_client_reuses_same_instance():
    _reset_opensearch_cache()
    fake_client = MagicMock(name="opensearch")

    with (
        patch.dict(
            "os.environ",
            {
                "OPENSEARCH_HOST": "example.aoss.amazonaws.com",
                "OPENSEARCH_PORT": "443",
                "OPENSEARCH_USE_SSL": "true",
                "AWS_REGION": "us-east-1",
            },
            clear=False,
        ),
        patch("repositories.opensearch.boto3.Session") as mock_session,
        patch("repositories.opensearch.AWSV4SignerAuth"),
        patch(
            "repositories.opensearch.OpenSearch",
            return_value=fake_client,
        ) as mock_opensearch,
    ):
        mock_session.return_value.get_credentials.return_value = MagicMock()
        first = opensearch_repo.opensearch_client()
        second = opensearch_repo.opensearch_client()

    assert first is second
    assert first is fake_client
    mock_opensearch.assert_called_once()
    _reset_opensearch_cache()


def test_opensearch_client_alias_returns_same_singleton():
    _reset_opensearch_cache()
    fake_client = MagicMock(name="opensearch")

    with (
        patch.dict(
            "os.environ",
            {"OPENSEARCH_HOST": "example.aoss.amazonaws.com"},
            clear=False,
        ),
        patch("repositories.opensearch.boto3.Session") as mock_session,
        patch("repositories.opensearch.AWSV4SignerAuth"),
        patch(
            "repositories.opensearch.OpenSearch",
            return_value=fake_client,
        ),
    ):
        mock_session.return_value.get_credentials.return_value = MagicMock()
        via_public = opensearch_repo.opensearch_client()
        via_alias = opensearch_repo._opensearch_client()

    assert via_public is via_alias
    _reset_opensearch_cache()
