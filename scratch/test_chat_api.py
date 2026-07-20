import requests

url = "http://localhost:8080/api/chat"
payload = {
    "query": "giải bài 1 trang 15 tập 1",
    "role": "student",
    "field": "math"
}

response = requests.post(url, json=payload)
data = response.json()
with open("scratch/output.txt", "w", encoding="utf-8") as f:
    f.write(data["response"])
print("Successfully wrote response to scratch/output.txt")
