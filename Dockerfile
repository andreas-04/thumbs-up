# Dockerfile for ThumbsUp using startup.py
# Runs the Flask web server via startup.py on port 8080

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for bash)
RUN apt-get update && apt-get install -y bash && rm -rf /var/lib/apt/lists/*

# Copy entire backend with all dependencies
COPY backend/ ./backend/
COPY startup.py ./startup.py
COPY docker-entrypoint.sh ./docker-entrypoint.sh

# Make scripts executable
RUN chmod +x ./docker-entrypoint.sh ./startup.py

# Install Python dependencies from backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Create necessary directories
RUN mkdir -p ./backend/apiv2/certs ./backend/apiv2/storage ./config

# Expose port 8080 for web access
EXPOSE 8080

# Default environment variables
ENV PREFERENCE=web
ENV WEB_PIN=1234
ENV ADMIN_PIN=1234
ENV SERVICE_NAME="ThumbsUp File Share"
ENV HOST=0.0.0.0
ENV PORT=8080

# Use entrypoint script to set up config and run startup.py
ENTRYPOINT ["./docker-entrypoint.sh"]
