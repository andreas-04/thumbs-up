# Dockerfile for ThumbsUp Backend API v2 Webserver
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
COPY start_webserver.sh ./start_webserver.sh

# Make start script executable
RUN chmod +x ./start_webserver.sh

# Create certs directory
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
ENV ADMIN_PIN=1234

# Entrypoint runs the start script (generates certs and starts server)
ENTRYPOINT ["./start_webserver.sh"]
