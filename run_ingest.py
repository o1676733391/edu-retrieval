from src.pipeline.ingest import run_ingest
import sys

if __name__ == "__main__":
    force = "--force" in sys.argv
    run_ingest(force_ocr=force)
