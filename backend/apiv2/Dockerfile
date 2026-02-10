# Dockerfile for ThumbsUp Backend API v2 Webserver
# TODO: Verify all COPY paths are correct when building from backend/apiv2 context
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY core/ ./core/
COPY services/ ./services/
COPY utils/ ./utils/
COPY templates/ ./templates/
COPY gen_selfsigned.py ./gen_selfsigned.py
# TODO: Replace start.sh with start_webserver.sh 
COPY start.sh ./start.sh

# Make start script executable
# TODO: Update this to chmod +x ./start_webserver.sh after fixing COPY above
RUN chmod +x ./start.sh

# TODO: Remove this mkdir - start_webserver.sh already creates certs dir and generates certs if missing
RUN mkdir -p ./certs

# Expose HTTPS port (Flask server runs on 8443 by default)
EXPOSE 8443

# Environment variables (default values, override with docker run -e)
ENV HOST=0.0.0.0
ENV PORT=8443
ENV STORAGE_PATH=./storage
ENV CERT_PATH=./certs/server_cert.pem
ENV KEY_PATH=./certs/server_key.pem
ENV TOKEN_EXPIRY_HOURS=24
ENV ENABLE_UPLOADS=true
ENV ENABLE_DELETE=false
ENV SERVICE_NAME="ThumbsUp File Share"
ENV MAX_UPLOAD_SIZE=104857600

# ADMIN_PIN MUST be set (either in docker run -e ADMIN_PIN=xxxx or in compose)
# No default value - failure is intentional if not provided

# Entrypoint runs the start script (generates certs and starts server)
# TODO: Update ENTRYPOINT to use start_webserver.sh: ["./start_webserver.sh"]
ENTRYPOINT ["./start.sh"]
