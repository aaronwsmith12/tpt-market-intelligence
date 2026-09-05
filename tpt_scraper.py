import csv
import requests
from bs4 import BeautifulSoup
import time
import json
import sys

query = sys.argv[1] if len(sys.argv) > 1 else "3rd grade multiplication games"
url = f"https://www.teacherspayteachers.com/Browse/Search:{query}"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

max_retries = 3
retry_delay = 5

response = None
for attempt in range(1, max_retries + 1):
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Attempt {attempt} failed: {e}")
        time.sleep(retry_delay)
        continue

    if response.status_code == 200:
        break
    elif response.status_code in (429, 500, 502, 503, 504):
        print(f"Got status {response.status_code}, retrying in {retry_delay}s (attempt {attempt}/{max_retries})...")
        time.sleep(retry_delay)
    else:
        print(f"Unexpected status code: {response.status_code}. Aborting.")
        exit(1)
else:
    print("Max retries exceeded. Aborting.")
    exit(1)

if response is None or response.status_code != 200:
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")

# Find the script tag containing the embedded page state (Apollo cache)
scripts = soup.find_all("script")
state_data = None
for script in scripts:
    if script.string and "var state = " in script.string:
        content = script.string
        start = content.find("var state = ") + len("var state = ")
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        state_data = json.loads(content[start:end])
        break

if not state_data:
    print("Could not locate embedded page data. Aborting.")
    exit(1)

apollo_state = state_data.get("apolloState", {})

# Only DigitalDownloadResource entries represent real listings with pricing;
# other Apollo cache entries are metadata/tags or bundle references without full data
resource_keys = [k for k in apollo_state.keys() if k.startswith("DigitalDownloadResource:")]

products = []
for key in resource_keys:
    item = apollo_state[key]
    pricing = item.get("pricing", {}).get("nonTransferableLicenses", {})
    price = pricing.get("salePrice") or pricing.get("price", "N/A")

    products.append({
        "Title": item.get("title", "N/A"),
        "Price": price,
        "Rating": item.get("overallQualityScore", "N/A"),
        "Reviews": item.get("totalEvaluations", "N/A"),
    })

# Drop bundle-referenced stub entries that have no pricing/rating data
products = [p for p in products if p["Price"] != "N/A"]

safe_query = query.replace(" ", "_")
filename = f"tpt_{safe_query}.csv"

with open(filename, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Title", "Price", "Rating", "Reviews"])
    writer.writeheader()
    writer.writerows(products)

print(f"Successfully extracted {len(products)} listings into {filename}")
