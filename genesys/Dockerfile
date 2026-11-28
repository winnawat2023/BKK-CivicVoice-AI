FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8080

# TLS is expected to be terminated by a load balancer / reverse proxy in front
# of this container. To terminate TLS in-process, add:
#   --ssl-keyfile /certs/key.pem --ssl-certfile /certs/cert.pem
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
