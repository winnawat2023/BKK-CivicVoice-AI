#!/usr/bin/env bash
# สคริปต์ตรวจสอบสภาพแวดล้อมบนเครื่อง DGX 101 (192.168.200.101)
# รันบนเครื่อง DGX 101: bash check_env.sh

echo "=================================================="
echo "  DGX 101 System & Environment Diagnostic Check  "
echo "=================================================="

echo -e "\n[1. ตรวจสอบการ์ดจอ NVIDIA GPU]"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv
else
    echo "❌ ไม่พบคำสั่ง nvidia-smi (ตรวจสอบ NVIDIA Driver)"
fi

echo -e "\n[2. ตรวจสอบ Nginx และพอร์ต 80 / 443]"
if command -v nginx &> /dev/null; then
    nginx -v
    sudo systemctl status nginx --no-pager | grep "Active:"
else
    echo "⚠️ Nginx ยังไม่ได้ติดตั้ง"
fi
echo "พอร์ตที่กำลังเปิดฟังอยู่ (Listening Ports):"
sudo ss -tulpn | grep -E ":(80|443|8000|22)\b" || sudo netstat -tuln | grep -E ":(80|443|8000|22)\b"

echo -e "\n[3. ตรวจสอบ Python & Docker]"
python3 --version
docker --version 2>/dev/null || echo "⚠️ Docker ยังไม่ได้ติดตั้ง"

echo -e "\n[4. ตรวจสอบการเชื่อมต่อไปยัง DGX 100 (192.168.200.100)]"
ping -c 2 192.168.200.100 || echo "❌ ไม่สามารถ ping ไปหา 192.168.200.100 ได้"

echo -e "\n=================================================="
echo "                  สิ้นสุดการตรวจสอบ                  "
echo "=================================================="
