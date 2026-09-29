import os

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection


def opensearch_client() -> OpenSearch:
    host = os.environ["OPENSEARCH_HOST"]
    port = int(os.environ.get("OPENSEARCH_PORT", "443"))
    use_ssl = os.environ.get("OPENSEARCH_USE_SSL", "true").lower() == "true"
    region = os.environ.get("AWS_REGION", "us-east-1")
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "aoss")

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=auth,
        use_ssl=use_ssl,
        verify_certs=use_ssl,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )


# Backward-compatible alias for existing call sites.
_opensearch_client = opensearch_client
