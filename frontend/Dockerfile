# Dockerfile for ThumbsUp Frontend
# This assumes a Python/Flask-based frontend, similar to backend/apiv2
# Adjust as needed for your actual frontend tech stack

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements (reuse backend/apiv2/requirements.txt for now)
COPY requirements.txt ./requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend source code (update this if you add frontend code)
COPY . .

# Expose port for port forwarding and remote access
EXPOSE 8080

# Copy and use start script
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

# Create certs directory (if not exists)
RUN mkdir -p /app/certs

# Entrypoint runs start script (generates/copies certs, starts server)
ENTRYPOINT ["./start.sh"]
