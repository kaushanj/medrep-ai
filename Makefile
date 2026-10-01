# SAM makefile builds for IngestFunction, IngestDependenciesLayer, and ApiFunction.
# CodeUri/ContentUri is the repo root so `sam build` finds this Makefile.

build-IngestFunction:
	mkdir -p "$(ARTIFACTS_DIR)/handlers"
	cp backend/handlers/__init__.py "$(ARTIFACTS_DIR)/handlers/"
	cp backend/handlers/s3_ingest.py "$(ARTIFACTS_DIR)/handlers/"

build-IngestDependenciesLayer:
	mkdir -p "$(ARTIFACTS_DIR)/python/services" "$(ARTIFACTS_DIR)/python/repositories"
	cp backend/services/__init__.py "$(ARTIFACTS_DIR)/python/services/"
	cp backend/services/ingest.py "$(ARTIFACTS_DIR)/python/services/"
	cp backend/services/rag.py "$(ARTIFACTS_DIR)/python/services/"
	cp backend/repositories/__init__.py "$(ARTIFACTS_DIR)/python/repositories/"
	cp backend/repositories/opensearch.py "$(ARTIFACTS_DIR)/python/repositories/"
	python -m pip install -r backend/requirements-ingest.txt -t "$(ARTIFACTS_DIR)/python"

# Package FastAPI for Lambda python3.12/x86_64 without a local Python 3.12.
# Downloads manylinux cp312 wheels (works on older Macs that only have newer Python).
build-ApiFunction:
	mkdir -p "$(ARTIFACTS_DIR)/api/schema" "$(ARTIFACTS_DIR)/services" "$(ARTIFACTS_DIR)/repositories" "$(ARTIFACTS_DIR)/utils"
	cp backend/main.py "$(ARTIFACTS_DIR)/"
	cp backend/api/__init__.py "$(ARTIFACTS_DIR)/api/"
	cp backend/api/auth.py "$(ARTIFACTS_DIR)/api/"
	cp backend/api/errors.py "$(ARTIFACTS_DIR)/api/"
	cp backend/api/middleware.py "$(ARTIFACTS_DIR)/api/"
	cp backend/api/rate_limit.py "$(ARTIFACTS_DIR)/api/"
	cp backend/api/schema/__init__.py "$(ARTIFACTS_DIR)/api/schema/"
	cp backend/api/schema/chat.py "$(ARTIFACTS_DIR)/api/schema/"
	cp backend/services/__init__.py "$(ARTIFACTS_DIR)/services/"
	cp backend/services/rag.py "$(ARTIFACTS_DIR)/services/"
	cp backend/repositories/__init__.py "$(ARTIFACTS_DIR)/repositories/"
	cp backend/repositories/opensearch.py "$(ARTIFACTS_DIR)/repositories/"
	cp backend/utils/__init__.py "$(ARTIFACTS_DIR)/utils/"
	cp backend/utils/constants.py "$(ARTIFACTS_DIR)/utils/"
	python3 -m pip install -r backend/requirements-api.txt -t "$(ARTIFACTS_DIR)" \
		--platform manylinux2014_x86_64 \
		--implementation cp \
		--python-version 3.12 \
		--only-binary=:all:
