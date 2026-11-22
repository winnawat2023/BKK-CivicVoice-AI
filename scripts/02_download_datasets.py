#!/usr/bin/env python3
"""
Step 2: Download priority datasets for 3-year BKK civic issue analysis.
Downloads:
1. Traffy Fondue 2569 (2026) parts 01-04 from BKK Open Data direct server.
2. Traffy Fondue 2568 (2025) and 2567 (2024) from Google Drive.
3. Call Center 1555 / Other civic complaint datasets.
"""

import os
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from bs4 import BeautifulSoup

RAW_DIR = "data/raw"
TRAFFY_DIR = os.path.join(RAW_DIR, "traffy_fondue")
COMPLAINTS_DIR = os.path.join(RAW_DIR, "complaints_1555")
os.makedirs(TRAFFY_DIR, exist_ok=True)
os.makedirs(COMPLAINTS_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def download_direct_url(url, dest_path, desc=""):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        print(f"   [Skip] {dest_path} already exists ({os.path.getsize(dest_path):,} bytes)")
        return True
    print(f"   [Download] {desc} -> {dest_path}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=120) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r      {downloaded:,} / {total_size:,} bytes ({percent:.1f}%)", end="", flush=True)
            print()
        print(f"   [Done] Saved {os.path.getsize(dest_path):,} bytes to {dest_path}")
        return True
    except Exception as e:
        print(f"\n   [Error] Failed to download {url}: {e}")
        return False

def download_drive_file(file_id, dest_path, desc=""):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        print(f"   [Skip] {dest_path} already exists ({os.path.getsize(dest_path):,} bytes)")
        return True
    print(f"   [Download Drive] {desc} (ID: {file_id}) -> {dest_path}")
    try:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        init_url = f"https://drive.google.com/uc?id={file_id}&export=download"
        req = urllib.request.Request(init_url, headers=HEADERS)
        res = opener.open(req)
        
        # Check if form exists
        soup = BeautifulSoup(res.read().decode("utf-8", errors="ignore"), "html.parser")
        form = soup.find("form")
        
        if form and form.get("action"):
            action = form.get("action")
            params = {}
            for inp in form.find_all("input"):
                if inp.get("name"):
                    params[inp.get("name")] = inp.get("value", "")
            final_url = f"{action}?{urllib.parse.urlencode(params)}"
        else:
            final_url = init_url
            
        req2 = urllib.request.Request(final_url, headers=HEADERS)
        with opener.open(req2, timeout=300) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 2 * 1024 * 1024 # 2MB chunks
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r      {downloaded:,} / {total_size:,} bytes ({percent:.1f}%)", end="", flush=True)
            print()
        print(f"   [Done] Saved {os.path.getsize(dest_path):,} bytes to {dest_path}")
        return True
    except Exception as e:
        print(f"\n   [Error] Failed to download Drive file {file_id}: {e}")
        return False

def main():
    print("=== Step 2: Downloading 3-Year Civic Datasets ===")

    # 1. Traffy Fondue 2569 (Current Year 2026) - Direct CSV from data.bangkok.go.th
    print("\n--- [1/3] Downloading Traffy Fondue 2569 (2026) Parts 1-4 ---")
    traffy_2569_parts = [
        ("sta_2569_part_01.csv", "https://data.bangkok.go.th/dataset/c3b94086-c586-4df7-8f03-004a7bbc1ddf/resource/3d759b36-9944-4f16-abb0-14c35520ff98/download/sta_2569_part_01.csv"),
        ("sta_2569_part_02.csv", "https://data.bangkok.go.th/dataset/c3b94086-c586-4df7-8f03-004a7bbc1ddf/resource/9a2d681f-4adc-4865-b46a-b4a69c2025e6/download/sta_2569_part_02.csv"),
        ("sta_2569_part_03.csv", "https://data.bangkok.go.th/dataset/c3b94086-c586-4df7-8f03-004a7bbc1ddf/resource/e9133c5e-8fed-464e-b79c-f37738071590/download/sta_2569_part_03.csv"),
        ("sta_2569_part_04.csv", "https://data.bangkok.go.th/dataset/c3b94086-c586-4df7-8f03-004a7bbc1ddf/resource/1ebb0e6d-b633-4bd9-b91d-cc562cfb974b/download/sta_2569_part_04.csv")
    ]
    for filename, url in traffy_2569_parts:
        dest = os.path.join(TRAFFY_DIR, filename)
        download_direct_url(url, dest, desc=filename)

    # 2. Traffy Fondue 2568 (2025) and 2567 (2024) from Google Drive
    print("\n--- [2/3] Downloading Traffy Fondue 2568 & 2567 from Google Drive ---")
    drive_datasets = [
        ("traffy_2568.csv", "1kJDdzkwhykAfEBwL49PW5OrRp3gxsz_R", "Traffy Fondue 2568 (2025) Full Dataset"),
        ("traffy_2567.csv", "1tW1MBfm1DNiA5fxARbNFhMLhhfWIBqn2", "Traffy Fondue 2567 (2024) Full Dataset")
    ]
    for filename, file_id, desc in drive_datasets:
        dest = os.path.join(TRAFFY_DIR, filename)
        download_drive_file(file_id, dest, desc=desc)

    # 3. Call Center 1555 and Specific Complaint Datasets
    print("\n--- [3/3] Downloading Call Center 1555 & Complaint Stats ---")
    complaint_datasets = [
        ("complaints_stat_2568.csv", "https://data.bangkok.go.th/dataset/85279d82-651c-4b77-a5c5-1333f9018afd/resource/ecca5f7e-a88f-4c2e-91fc-a5c4b2b828ea/download/004-694.csv", "สถิติการรับแจ้งเรื่องร้องเรียน (ชุดข้อมูล 2568)"),
        ("disabled_complaints_1555.csv", "https://data.bangkok.go.th/dataset/394e25cf-2170-477d-9a84-a682e7b2540d/resource/238b2f72-ac30-49d0-b202-71be66b13cb2/download/03-.-1555.csv", "สถิติเรื่องร้องเรียนร้องทุกข์ 1555"),
        ("complaint_actions_2566.csv", "https://data.bangkok.go.th/dataset/ea814cdf-2184-481a-83d4-5c952af28dc3/resource/fff38134-ebf0-4b3e-ad90-af5e2abad9b0/download/fff38134-ebf0-4b3e-ad90-af5e2abad9b0.csv", "สถิติการปฏิบัติงานด้านเรื่องร้องเรียน"),
        ("public_health_traffy_2569.csv", "https://data.bangkok.go.th/dataset/f0585ee1-43b4-4496-852f-948b14b61477/resource/96a1b3df-7463-4090-908c-f869c9ead49b/download/fondue2570cot.csv", "ข้อมูล Traffy Fondue เชิงพื้นที่สำนักอนามัย")
    ]
    for filename, url, desc in complaint_datasets:
        dest = os.path.join(COMPLAINTS_DIR, filename)
        download_direct_url(url, dest, desc=desc)

    print("\n=== Finished Step 2 Downloads ===")

if __name__ == "__main__":
    main()
