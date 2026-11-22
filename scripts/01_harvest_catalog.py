#!/usr/bin/env python3
"""
Step 1: Harvest full catalog metadata from data.bangkok.go.th via CKAN API.
"""

import urllib.request
import json
import time
import os
import sys

BASE_URL = "https://data.bangkok.go.th/api/3/action"
CATALOG_DIR = "data/catalog"
os.makedirs(CATALOG_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def harvest_catalog():
    print("[1/3] Fetching package list...")
    list_url = f"{BASE_URL}/package_list"
    data = fetch_json(list_url)
    if not data.get("success"):
        print("Failed to fetch package list!")
        sys.exit(1)
        
    package_names = data.get("result", [])
    total = len(package_names)
    print(f"Total packages discovered: {total}")
    
    # Save package names
    with open(f"{CATALOG_DIR}/package_names.json", "w", encoding="utf-8") as f:
        json.dump(package_names, f, ensure_ascii=False, indent=2)

    print("[2/3] Fetching package details with resources...")
    # Fetch packages with resources in batches using current_package_list_with_resources
    all_packages = []
    limit = 100
    offset = 0
    
    while offset < total:
        print(f"   Fetching packages {offset + 1} to {min(offset + limit, total)} of {total}...")
        batch_url = f"{BASE_URL}/current_package_list_with_resources?limit={limit}&offset={offset}"
        try:
            batch_data = fetch_json(batch_url)
            if batch_data.get("success"):
                results = batch_data.get("result", [])
                if not results:
                    break
                all_packages.extend(results)
                offset += len(results)
            else:
                print(f"   Warning: batch at offset {offset} failed")
                offset += limit
        except Exception as e:
            print(f"   Error fetching batch offset {offset}: {e}")
            time.sleep(2)
            offset += limit
        time.sleep(0.5)

    print(f"Successfully harvested {len(all_packages)} package metadata records.")

    # Save full catalog
    out_file = f"{CATALOG_DIR}/bkk_catalog_all.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_packages, f, ensure_ascii=False, indent=2)
    print(f"Saved full catalog to {out_file}")

    print("[3/3] Filtering 3-year relevant datasets (2567-2569 / 2024-2026)...")
    curated = []
    keywords = [
        "traffy", "fondue", "ร้องเรียน", "1555", "ปัญหา", "อุบัติเหตุ", "น้ำท่วม", 
        "ขยะ", "จราจร", "ทางเท้า", "ถนน", "แสงสว่าง", "ฝุ่น", "pm2.5", "pm 2.5",
        "2567", "2568", "2569", "2024", "2025", "2026"
    ]
    
    for pkg in all_packages:
        title = pkg.get("title", "")
        notes = pkg.get("notes", "") or ""
        name = pkg.get("name", "")
        combined_text = f"{title} {notes} {name}".lower()
        
        matches = [kw for kw in keywords if kw in combined_text]
        if matches:
            resources = []
            for r in pkg.get("resources", []):
                resources.append({
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "format": r.get("format", "").upper(),
                    "url": r.get("url"),
                    "size": r.get("size"),
                    "created": r.get("created"),
                    "last_modified": r.get("last_modified")
                })
            
            curated.append({
                "id": pkg.get("id"),
                "name": name,
                "title": title,
                "org": pkg.get("organization", {}).get("title") if pkg.get("organization") else None,
                "matched_keywords": matches,
                "metadata_modified": pkg.get("metadata_modified"),
                "resources_count": len(resources),
                "resources": resources
            })

    curated_file = f"{CATALOG_DIR}/curated_datasets_3years.json"
    with open(curated_file, "w", encoding="utf-8") as f:
        json.dump(curated, f, ensure_ascii=False, indent=2)
        
    print(f"Curated {len(curated)} civic-relevant datasets saved to {curated_file}")

if __name__ == "__main__":
    harvest_catalog()
