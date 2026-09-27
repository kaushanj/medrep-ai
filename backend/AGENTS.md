# Backend Instructions

The backend uses Python and FastAPI.

## General

- Keep code simple and readable.
- Follow existing backend structure and conventions.
- Do not add unrelated features.
- Do not add new dependencies unless needed.
- Do not hardcode secrets or AWS credentials.

## API

- Use FastAPI for API routes.
- Use Pydantic models for request and response validation.
- Keep route handlers small.
- Move business logic into service modules when needed.
- Return clear HTTP status codes and error responses.

## Testing

- Follow the project's testing conventions.

- Prefer pytest for backend tests.
- Test API behavior, validation, status codes, and responses.
- Do not weaken tests just to make them pass.

## Project Structure

Keep backend code under `backend/`.

As the project grows, prefer separation such as:

backend/
├── main.py
├── api/
├── models/
├── services/
├── repositories/
├── utils/
└── tests/

Do not create these folders unless the current issue needs them.

## AWS

When working with AWS:

- use environment variables or IAM roles
- never commit credentials
- keep AWS-specific code separated from API routes where practical

## Documentation

For backend architecture or API changes, read the relevant files under `docs/`.

Update documentation only when the issue changes:
- API contracts
- backend architecture
- important backend decisions