# Dockerfile for ThumbsUp Backend API v2 Webserver
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY models.py ./models.py
COPY core/ ./core/
COPY services/ ./services/
COPY utils/ ./utils/
COPY templates/ ./templates/
COPY gen_selfsigned.py ./gen_selfsigned.py
COPY start_webserver.sh ./start_webserver.sh

# Make start script executable
RUN chmod +x ./start_webserver.sh

# Create necessary directories
RUN mkdir -p ./certs ./storage ./data

# Expose HTTPS port (Flask server runs on 8443 by default)
EXPOSE 8443

# Environment variables (default values, override with docker run -e)
ENV HOST=0.0.0.0
ENV PORT=8443
ENV STORAGE_PATH=/app/storage
ENV CERT_PATH=/app/certs/server_cert.pem
ENV KEY_PATH=/app/certs/server_key.pem
ENV DATABASE_URI=sqlite:////app/data/thumbsup.db
ENV TOKEN_EXPIRY_HOURS=24
ENV ENABLE_UPLOADS=true
ENV ENABLE_DELETE=false
ENV SERVICE_NAME="ThumbsUp File Share"
ENV MAX_UPLOAD_SIZE=104857600

# ADMIN_PIN MUST be set (either in docker run -e ADMIN_PIN=xxxx or in compose)
# No default value - failure is intentional if not provided

# Volume for persistent data
VOLUME ["/app/storage", "/app/data"]

# Entrypoint runs the start script (generates certs, initializes DB, starts server)
ENTRYPOINT ["./start_webserver.sh"]
