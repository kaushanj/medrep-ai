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
├    ├──schema/
├── models/
├── services/
├── repositories/
├── utils/
└── tests/

Do not create these folders unless the current issue needs them.

## Docker

The backend should be containerized with Docker.

When Docker setup does not exist yet:

- Create a `Dockerfile` for the FastAPI backend.
- Add a `.dockerignore` file.
- Run the FastAPI application inside the Docker container.
- Expose the application port from the container.
- Use environment variables for configuration.
- Do not copy secrets, `.env` files, AWS credentials, or unnecessary files into the image.
- Use the existing Python dependency file such as `requirements.txt` or `pyproject.toml`.
- Keep the Docker setup simple.
- Do not introduce Docker Compose unless multiple services require it.
- FastAPI must listen on `0.0.0.0` inside the container.

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