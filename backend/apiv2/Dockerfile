FROM python:3.11-slim

# Install system dependencies for mDNS (Avahi)
RUN apt-get update && apt-get install -y \
    avahi-daemon \
    avahi-utils \
    dbus \
    libdbus-1-dev \
    libavahi-client-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p /app/storage /app/certs /app/static /app/templates

# Generate self-signed certificates if they don't exist
RUN python generate_certs.py --cert-path /app/certs/server_cert.pem --key-path /app/certs/server_key.pem || true

# Expose HTTPS port
EXPOSE 8443

# Start Avahi daemon and server
CMD ["sh", "-c", "service dbus start && service avahi-daemon start && python server.py"]
