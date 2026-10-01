# MedRep API deployment (SAM)

Deploy the synchronous FastAPI web API as:

**API Gateway HTTP API → Lambda (`medrep-api`) → Mangum → FastAPI → Bedrock + OpenSearch Serverless**

This stack is **separate** from PDF ingestion (`infra/ingest-template.yaml` / `infra/template.yaml`). Do not replace or merge the ingestion template.

Template: `infra/api-template.yaml`

## 1. Prerequisites

- AWS account with permission to create Lambda, API Gateway HTTP API, IAM roles, and CloudWatch Logs
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) and AWS CLI configured (`aws login` / credentials)
- Existing OpenSearch Serverless collection/index (`medrep-index` by default) and Bedrock model access in the target region
- Google OAuth **Web** Client ID (same audience as frontend `NEXT_PUBLIC_GOOGLE_CLIENT_ID`)
- AWS SAM CLI (project venv is fine: `backend/.venv/bin/sam`)
- Local Python 3.12 is **not** required: the API package uses a Makefile build that downloads Linux Python 3.12 wheels

Do not commit `.env` files, AWS keys, Google client secrets, or bearer tokens.

## 2. Values you must provide

| Parameter | Source / default |
| --- | --- |
| `GoogleClientId` | Your Google OAuth Web Client ID (required) |
| `CorsAllowedOrigins` | Comma-separated origins (e.g. `http://localhost:3000`); empty denies browser CORS |
| `OpenSearchHost` | AOSS collection hostname only (no `https://`) |
| `OpenSearchIndex` | Default `medrep-index` |
| `OpenSearchPort` | Default `443` |
| `OpenSearchUseSsl` | Default `true` |
| `BedrockEmbeddingModelId` | Default `amazon.titan-embed-text-v2:0` |
| `BedrockGenerationModelId` | Default `amazon.nova-lite-v1:0` |

AWS region comes from your CLI/SAM deploy configuration (`AWS_REGION` / guided prompts). The Lambda uses the execution role for Bedrock and OpenSearch — no access keys in the template.

## 3. Validate

From the repository root:

```bash
sam validate --template-file infra/api-template.yaml
```

## 4. Build

From the repository root (venv SAM is OK on an older Mac):

```bash
backend/.venv/bin/sam build --template-file infra/api-template.yaml
```

This runs the repo-root `Makefile` target `build-ApiFunction`, which copies the FastAPI app and installs `backend/requirements-api.txt` as **manylinux / cp312** wheels for Lambda. You do not need to install Python 3.12 on the laptop.

Note: `sam build` writes to the shared `.aws-sam/` directory. Building the API stack overwrites a previous ingest build artifact set (and vice versa). Rebuild the stack you intend to deploy immediately before `sam deploy`.

## 5. Deploy

After a successful build, either:

```bash
sam deploy --guided --template-file .aws-sam/build/template.yaml
```

or (SAM uses the last build by default):

```bash
sam deploy --guided
```

Suggested stack name: `medrep-api` (keep this distinct from the ingestion stack name).

When prompted, supply the parameters in section 2. Do not paste secrets into git or chat logs.

Example non-guided shape (fill in your values; do not commit real values):

```bash
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name medrep-api \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    'GoogleClientId=YOUR_GOOGLE_CLIENT_ID' \
    'CorsAllowedOrigins=http://localhost:3000' \
    'OpenSearchHost=YOUR_COLLECTION.REGION.aoss.amazonaws.com'
```

## 6. Get the deployed API URL

```bash
aws cloudformation describe-stacks \
  --stack-name medrep-api \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text
```

Or open the stack **Outputs** in the AWS Console: `ApiUrl`, `ApiFunctionArn`, `ApiFunctionRoleArn`.

Point the frontend `NEXT_PUBLIC_API_BASE_URL` at `ApiUrl` (no trailing path beyond the base URL; routes are `/health` and `/chat`).

## 7. Test `GET /health`

```bash
curl -sS -D - "$(aws cloudformation describe-stacks --stack-name medrep-api --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)health"
```

Expect HTTP 200 and a body like `{"status":"ok"}`.

## 8. Verify unauthenticated `POST /chat` returns 401

```bash
API_URL="$(aws cloudformation describe-stacks --stack-name medrep-api --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)"
curl -sS -D - -X POST "${API_URL}chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is this product used for?"}'
```

Expect HTTP 401 (missing Bearer token). Do not log or commit tokens when you later test authenticated chat.

## 9. Add the Lambda role to the OpenSearch Serverless data-access policy

IAM `aoss:APIAccessAll` on the Lambda role is necessary but often **not sufficient** for AOSS.

1. Read the output `ApiFunctionRoleArn` from the `medrep-api` stack.
2. In **Amazon OpenSearch Service → Serverless → Data access policies**, edit the existing policy that already grants your ingest role / principals access to the collection/index.
3. Add a principal for that **exact** `ApiFunctionRoleArn`.
4. Keep index/collection permissions aligned with what the chat API needs (search/read on `medrep-index`). Do **not** create a new collection or index for this stack.

Until this step is done, `/health` may succeed while authenticated `/chat` fails when querying OpenSearch.

## 10. Redeploy later

```bash
sam build --template-file infra/api-template.yaml
sam deploy --stack-name medrep-api --template-file .aws-sam/build/template.yaml --capabilities CAPABILITY_IAM
```

Reuse the same stack name and parameter values (or a saved `samconfig.toml` locally — that file is gitignored via `*.toml` in this repo).

## 11. Delete only this API stack

```bash
aws cloudformation delete-stack --stack-name medrep-api
aws cloudformation wait stack-delete-complete --stack-name medrep-api
```

This removes the HTTP API, `medrep-api` Lambda, its execution role, and the API log group defined in this template.

It does **not** delete:

- the ingestion stack / `medrep-s3-ingest` Lambda
- the product PDF S3 bucket
- the OpenSearch Serverless collection or `medrep-index`
- Bedrock guardrails or models

After delete, remove the retired `ApiFunctionRoleArn` from the AOSS data-access policy if you added it in section 9.
