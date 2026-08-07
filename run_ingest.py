from src.pipeline.ingest import run_ingest
import sys
import json

if __name__ == "__main__":
    force = "--force" in sys.argv
    field_arg = "math"
    topics_arg = None

    for arg in sys.argv:
        if arg.startswith("--field="):
            field_arg = arg.split("=", 1)[1]
        elif arg.startswith("--topics="):
            raw_topics = arg.split("=", 1)[1]
            try:
                topics_arg = json.loads(raw_topics)
            except Exception as e:
                print(f"[Warning] Could not parse --topics JSON: {e}")
        elif arg.startswith("--topics-file="):
            filepath = arg.split("=", 1)[1]
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    topics_arg = json.load(f)
            except Exception as e:
                print(f"[Warning] Could not read --topics-file '{filepath}': {e}")

    run_ingest(force_ocr=force, field=field_arg, topics=topics_arg)
