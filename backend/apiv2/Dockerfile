FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY services/ ./services/
COPY utils/ ./utils/
COPY templates/ ./templates/
COPY gen_selfsigned.py ./gen_selfsigned.py
RUN mkdir -p ./certs && python gen_selfsigned.py --output-dir ./certs

EXPOSE 8443

ENV HOST=0.0.0.0
ENV PORT=8443
ENV STORAGE_PATH=./storage
ENV ENABLE_UPLOADS=true
ENV ENABLE_DELETE=false
ENV SERVICE_NAME="ThumbsUp File Share"
ENV MAX_UPLOAD_SIZE=104857600

# Defaults for cert paths (can be overridden at runtime)
ENV CERT_PATH=./certs/server_cert.pem
ENV KEY_PATH=./certs/server_key.pem
ENV TOKEN_EXPIRY_HOURS=24

# ADMIN_PIN MUST be set at runtime

CMD ["python3", "-m", "core.server"]
