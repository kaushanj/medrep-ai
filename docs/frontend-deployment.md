# MedRep AI frontend deployment (CloudFront + S3)

Host the Next.js **static export** as:

**CloudFront → private S3 bucket (OAC) → `frontend/out/`**

This stack is **separate** from the API (`infra/api-template.yaml`) and PDF ingestion (`infra/ingest-template.yaml`). Do not merge these stacks.

Template: `infra/frontend-template.yaml`

The app is client-side React (Google Identity Services + browser `fetch`). It does not use Next.js API routes, middleware, or server-only features, so `output: "export"` is appropriate.

## 1. Prerequisites

- AWS account with permission to create S3 buckets, CloudFront distributions, and IAM-style bucket policies
- AWS CLI configured (`aws login` / credentials)
- Node.js 18+ (for `npm install` / `npm run build`)
- Deployed MedRep API stack (or another reachable API base URL) — see [api-deployment.md](api-deployment.md)
- Google OAuth **Web** Client ID (same value as API `GoogleClientId` / local `NEXT_PUBLIC_GOOGLE_CLIENT_ID`)

Do not commit `.env.local`, AWS keys, Google client secrets, or bearer tokens. The frontend only needs the **public** OAuth client ID (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`).

## 2. Deploy the frontend CloudFormation stack

From the repository root (no SAM build step — this template is plain CloudFormation):

```bash
aws cloudformation deploy \
  --template-file infra/frontend-template.yaml \
  --stack-name medrep-frontend
```

Suggested stack name: `medrep-frontend` (keep it distinct from `medrep-api` and the ingestion stack).

Validate optionally:

```bash
aws cloudformation validate-template \
  --template-body file://infra/frontend-template.yaml
```

## 3. Read stack outputs

```bash
aws cloudformation describe-stacks \
  --stack-name medrep-frontend \
  --query "Stacks[0].Outputs" \
  --output table
```

Useful outputs:

| Output | Use |
| --- | --- |
| `FrontendBucketName` | Target for `aws s3 sync` |
| `CloudFrontDistributionId` | Cache invalidations |
| `CloudFrontURL` | Browser origin (`https://…cloudfront.net`) |
| `CloudFrontDomainName` | Domain only (no scheme) |

Helpers:

```bash
BUCKET="$(aws cloudformation describe-stacks \
  --stack-name medrep-frontend \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)"

DIST_ID="$(aws cloudformation describe-stacks \
  --stack-name medrep-frontend \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
  --output text)"

CF_URL="$(aws cloudformation describe-stacks \
  --stack-name medrep-frontend \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" \
  --output text)"

echo "Bucket=$BUCKET"
echo "DistributionId=$DIST_ID"
echo "URL=$CF_URL"
```

## 4. Get the deployed API Gateway URL

From the API stack (default name `medrep-api`):

```bash
aws cloudformation describe-stacks \
  --stack-name medrep-api \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text
```

Use that value as `NEXT_PUBLIC_API_BASE_URL` (include the trailing slash if the stack output has one; the frontend trims extra trailing slashes). Routes are `/health` and `/chat` relative to that base.

## 5. Create production `.env.local` and build

```bash
cd frontend
cp .env.example .env.local
```

Edit `.env.local` (do **not** commit this file):

```text
NEXT_PUBLIC_API_BASE_URL=<deployed API Gateway URL>
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<existing Google Web Client ID>
```

Notes:

- `NEXT_PUBLIC_*` values are baked into the static build at `npm run build` time.
- Use only the Google **Web Client ID** (public). Do not put client secrets or AWS credentials in the frontend.
- Rebuild after changing either variable.

Then:

```bash
cd frontend
npm install
npm run build
```

Confirm `frontend/out/index.html` exists.

## 6. Upload the static export to S3

From the repository root (substitute your bucket name, or use `$BUCKET` from section 3):

```bash
aws s3 sync frontend/out/ s3://BUCKET_NAME --delete
```

Example with the stack output:

```bash
aws s3 sync frontend/out/ "s3://${BUCKET}" --delete
```

`--delete` removes objects in the bucket that are no longer in `frontend/out/`.

## 7. Invalidate CloudFront after a redeploy

After uploading new files:

```bash
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/*"
```

Example:

```bash
aws cloudfront create-invalidation \
  --distribution-id "${DIST_ID}" \
  --paths "/*"
```

## 8. Open the CloudFront URL

```bash
echo "$CF_URL"
```

Or read `CloudFrontURL` from stack outputs / the AWS Console. Open that `https://…cloudfront.net` URL in a browser.

## 9. Update Google OAuth Authorized JavaScript Origins

1. Open [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials.
2. Edit the same **Web application** OAuth client used for local/dev.
3. Under **Authorized JavaScript origins**, add:

```text
https://CLOUDFRONT_DOMAIN
```

Use the exact CloudFront origin (scheme + host), matching `CloudFrontURL` — for example `https://d111111abcdef8.cloudfront.net`.

4. Keep `http://localhost:3000` for local development if you still use it.
5. You do not need Authorized redirect URIs for the GIS button / ID token flow used here.

## 10. Update API CORS (`CorsAllowedOrigins`)

The API stack must allow the CloudFront origin. Redeploy or update the `medrep-api` stack parameter `CorsAllowedOrigins` to include the same origin as Google (no trailing slash), for example:

```text
https://CLOUDFRONT_DOMAIN
```

Comma-separated list if you also allow localhost:

```text
http://localhost:3000,https://CLOUDFRONT_DOMAIN
```

Example shape (fill in your real values; do not commit them):

```bash
sam build --template-file infra/api-template.yaml
sam deploy \
  --stack-name medrep-api \
  --template-file .aws-sam/build/template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    'GoogleClientId=YOUR_GOOGLE_CLIENT_ID' \
    'CorsAllowedOrigins=https://YOUR_CLOUDFRONT_DOMAIN' \
    'OpenSearchHost=YOUR_COLLECTION.REGION.aoss.amazonaws.com'
```

See [api-deployment.md](api-deployment.md) for full API deploy steps.

## 11. Rebuild / redeploy frontend changes

Whenever you change UI code or `NEXT_PUBLIC_*` env values:

```bash
cd frontend
npm run build
cd ..
aws s3 sync frontend/out/ s3://BUCKET_NAME --delete
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/*"
```

Infrastructure changes only (rare): redeploy `infra/frontend-template.yaml` with the same stack name.

## 12. Delete only the frontend stack

Empty the bucket first (CloudFormation cannot delete a non-empty bucket by default):

```bash
aws s3 rm "s3://${BUCKET}" --recursive
```

Then:

```bash
aws cloudformation delete-stack --stack-name medrep-frontend
aws cloudformation wait stack-delete-complete --stack-name medrep-frontend
```

This removes the frontend S3 bucket, CloudFront distribution, OAC, and bucket policy defined in this template.

It does **not** delete:

- the API stack / `medrep-api` Lambda / HTTP API
- the ingestion stack / product PDF bucket
- OpenSearch Serverless or Bedrock resources

After delete, remove the retired CloudFront origin from Google Authorized JavaScript Origins and from the API `CorsAllowedOrigins` parameter if you no longer need it.

## Security checklist

- S3 remains private (Block Public Access on; no public-read ACL; no S3 website hosting)
- CloudFront reads the bucket only via Origin Access Control (OAC)
- Do not commit `.env.local`
- Do not put Google client secrets or AWS credentials in frontend code or env files checked into git
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is the public OAuth client ID only
