# SAM makefile builds for IngestFunction and IngestDependenciesLayer.
# CodeUri/ContentUri is the repo root so `sam build --use-container` mounts
# backend/ and can copy sources + install deps inside the Lambda build image.

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
