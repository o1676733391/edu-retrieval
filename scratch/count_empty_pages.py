import json

with open("data/processed_book_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

v1_empty = [p["pdf_page_index"] for p in data if p["volume"] == "1" and (not p["text"] or not p["text"].strip())]
v2_empty = [p["pdf_page_index"] for p in data if p["volume"] == "2" and (not p["text"] or not p["text"].strip())]

print("Volume 1 empty pages count:", len(v1_empty))
print("Volume 1 empty page indices:", v1_empty)
print("-" * 50)
print("Volume 2 empty pages count:", len(v2_empty))
print("Volume 2 empty page indices:", v2_empty)
