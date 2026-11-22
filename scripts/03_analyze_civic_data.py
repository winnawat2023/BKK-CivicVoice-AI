#!/usr/bin/env python3
"""
Step 3: Analyze 3-Year BKK Civic Problem Data (2.26M records)
Generates:
1. Top Problem Categories (overall & trend by year)
2. District Breakdown & Bottlenecks
3. Resolution Rate & SLA Performance
4. Key Actionable Insights for Hackathon
"""

import os
import glob
import csv
from collections import Counter, defaultdict
import json

DATA_DIR = "opendata/raw/traffy_fondue"
OUT_DIR = "opendata/processed"
os.makedirs(OUT_DIR, exist_ok=True)

def analyze():
    print("=== Analyzing 3-Year BKK Civic Issues (2567-2569) ===")
    
    total_records = 0
    type_counts = Counter()
    district_counts = Counter()
    state_counts = Counter()
    year_type_counts = defaultdict(Counter)
    district_unresolved = Counter()
    
    # Process files
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    print(f"Found {len(files)} CSV files to process...")

    for filepath in files:
        filename = os.path.basename(filepath)
        print(f"   Processing {filename}...")
        
        # Determine year
        if "2569" in filename:
            year = "2569"
        elif "2568" in filename:
            year = "2568"
        elif "2567" in filename:
            year = "2567"
        else:
            year = "Unknown"
            
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_records += 1
                
                # Clean type / category
                raw_type = row.get("type") or "ไม่ระบุ"
                types = [t.strip() for t in raw_type.replace("{", "").replace("}", "").replace('"', '').split(",") if t.strip()]
                for t in types:
                    type_counts[t] += 1
                    year_type_counts[year][t] += 1
                
                # District
                district = (row.get("district") or "").strip()
                if district:
                    district_counts[district] += 1
                    
                # State / status
                state = (row.get("state") or "").strip()
                if state:
                    state_counts[state] += 1
                    if state in ["รอรับเรื่อง", "กำลังดำเนินการ", "ส่งต่อ"]:
                        district_unresolved[district] += 1

    print(f"\nFinished parsing {total_records:,} records.")

    # Prepare summary results
    top_types = type_counts.most_common(15)
    top_districts = district_counts.most_common(15)
    
    # Calculate resolution rate per top district
    district_resolution = []
    for dist, count in district_counts.most_common(20):
        unres = district_unresolved[dist]
        resolved = count - unres
        rate = (resolved / count) * 100 if count > 0 else 0
        district_resolution.append({
            "district": dist,
            "total_issues": count,
            "unresolved": unres,
            "resolution_rate_pct": round(rate, 2)
        })

    summary = {
        "total_records": total_records,
        "state_breakdown": dict(state_counts.most_common()),
        "top_15_problem_types": [{"type": t, "count": c} for t, c in top_types],
        "top_15_districts": [{"district": d, "count": c} for d, c in top_districts],
        "district_resolution_sample": district_resolution,
        "yearly_trends_top_5": {
            y: [{"type": t, "count": c} for t, c in year_type_counts[y].most_common(5)]
            for y in ["2567", "2568", "2569"]
        }
    }

    out_json = os.path.join(OUT_DIR, "bkk_civic_analysis_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Summary JSON saved to {out_json}")

    return summary

if __name__ == "__main__":
    analyze()
