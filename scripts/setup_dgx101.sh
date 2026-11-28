#!/usr/bin/env bash
# สคริปต์ติดตั้งและ Deploy BKK CivicVoice AI Backend & SSL บนเครื่อง DGX 101 (192.168.200.101)
# รันด้วยคำสั่ง: bash setup_dgx101.sh

set -e

echo "=== 1. อัปเดตแพ็กเกจและติดตั้ง Nginx, Certbot, Git, Python ==="
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx git python3-pip python3-venv

echo "=== 2. ดึงโค้ดโปรเจกต์จาก GitHub ==="
cd /opt
if [ -d "BKK-CivicVoice-AI" ]; then
    echo "Updating existing repository..."
    cd BKK-CivicVoice-AI
    git pull origin main
else
    sudo git clone https://github.com/winnawat2023/BKK-CivicVoice-AI.git
    cd BKK-CivicVoice-AI
    sudo chown -R $USER:$USER /opt/BKK-CivicVoice-AI
fi

echo "=== 3. ติดตั้ง Virtual Environment และ Python Dependencies ==="
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r src/backend/requirements.txt

echo "=== 4. สร้าง Systemd Service ให้ FastAPI รันตลอดเวลาแบบ Background ==="
sudo tee /etc/systemd/system/civicvoice.service << EOF
[Unit]
Description=BKK CivicVoice AI Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=/opt/BKK-CivicVoice-AI
ExecStart=/opt/BKK-CivicVoice-AI/venv/bin/python -m uvicorn src.backend.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable civicvoice
sudo systemctl restart civicvoice

echo "=== 5. ออกใบรับรอง SSL ฟรีด้วย Certbot (Let's Encrypt) ==="
# ออก SSL สำหรับ voiceai-demo.ark-insights.com
sudo certbot --nginx -d voiceai-demo.ark-insights.com --non-interactive --agree-tos -m h.chaiyaporn@ark-insights.com || echo "⚠️ หาก Certbot ติดปัญหา ให้ตรวจสอบว่า DNS A-Record ชี้มาที่ Public IP ถูกต้องแล้ว"

echo "=== 6. ตั้งค่า Nginx Reverse Proxy ไปหา FastAPI พอร์ต 8000 ==="
sudo tee /etc/nginx/sites-available/voiceai << 'EOF'
server {
    server_name voiceai-demo.ark-insights.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Location สำหรับ Widget หน้าจอ Agent
    location /widget/ {
        alias /opt/BKK-CivicVoice-AI/src/frontend/widget/;
        index index.html;
    }

    listen 80;
}
EOF

sudo ln -sf /etc/nginx/sites-available/voiceai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "=== ติดตั้งเสร็จสิ้น! ทดสอบเข้าใช้งานได้ที่ https://voiceai-demo.ark-insights.com ==="
