#!/usr/bin/env python3
"""
End-to-End Simulation Script for BKK CivicVoice AI.
Simulates Genesys Cloud CX Inbound Voice Call triggering Webhook to Backend.
"""

import urllib.request
import json
import time

URL = "http://127.0.0.1:8000/api/v1/genesys/webhook"

test_cases = [
    {
        "desc": "Case 1: แจ้งปัญหาถนน/ทางเท้าชำรุด (สุขุมวิท 50 คลองเตย)",
        "payload": {
            "interaction_id": "CALL-9042-DEMO",
            "ani": "084-768-5368",
            "channel": "voice",
            "transcript": "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก น้ำเอ่อท่วมถนน มอเตอร์ไซค์ล้มไปคันนึงแล้ว อันตรายมาก ช่วยส่งคนมาดูหน่อยครับ"
        }
    },
    {
        "desc": "Case 2: สอบถามระเบียบการทำบัตรประชาชน (Auto Q&A)",
        "payload": {
            "interaction_id": "CALL-9043-DEMO",
            "ani": "081-234-5678",
            "channel": "voice",
            "transcript": "สอบถามหน่อยครับ วันเสาร์นี้สำนักงานเขตจตุจักรเปิดทำบัตรประชาชนไหมครับ แล้วต้องเตรียมเอกสารอะไรไปบ้าง"
        }
    }
]

def run_simulation():
    print("=== Testing BKK CivicVoice AI Middleware End-to-End ===\n")
    failed = False
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    for tc in test_cases:
        print(f"--- Running {tc['desc']} ---")
        req = urllib.request.Request(
            URL,
            data=json.dumps(tc["payload"]).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                print(f"Status: {resp.status} OK")
                print("Result:")
                print(json.dumps(res, ensure_ascii=False, indent=2))
        except (OSError, ValueError) as e:
            failed = True
            print(f"Error connecting to backend: {e}")
            print("Hint: Start feature/backend on port 8000 using docs/runtime-integration.md")
        print("\n" + "="*50 + "\n")
        time.sleep(1)
    return not failed

if __name__ == "__main__":
    raise SystemExit(0 if run_simulation() else 1)

