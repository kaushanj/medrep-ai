"""CLI shim: ``python ingest.py ...`` delegates to ``services.ingest.main``."""

from services.ingest import main

if __name__ == "__main__":
    raise SystemExit(main())
