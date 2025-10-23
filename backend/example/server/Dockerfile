# Use Ubuntu as base image
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, Avahi, and dependencies
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    avahi-daemon \
    avahi-utils \
    dbus \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure Avahi to work in container
RUN mkdir -p /var/run/dbus && \
    mkdir -p /var/run/avahi-daemon

# Set working directory
WORKDIR /app

# Copy the server script from example/server/
COPY example/server/mtls_server.py .

# Copy certificates from pki directory
COPY pki/server_cert.pem ./server_cert.pem
COPY pki/server_key.pem ./server_key.pem
COPY pki/client_cert.pem ./client_cert.pem

# Update the certificate paths in the script to use current directory
RUN sed -i "s|certfile='../../pki/server_cert.pem'|certfile='./server_cert.pem'|g" mtls_server.py && \
    sed -i "s|keyfile='../../pki/server_key.pem'|keyfile='./server_key.pem'|g" mtls_server.py && \
    sed -i "s|cafile='../../pki/client_cert.pem'|cafile='./client_cert.pem'|g" mtls_server.py && \
    sed -i "s|'../../pki/server_cert.pem'|'./server_cert.pem'|g" mtls_server.py && \
    sed -i "s|'../../pki/server_key.pem'|'./server_key.pem'|g" mtls_server.py && \
    sed -i "s|'../../pki/client_cert.pem'|'./client_cert.pem'|g" mtls_server.py

# Expose the mTLS port
EXPOSE 8443

# Expose mDNS port
EXPOSE 5353/udp

# Start script to run both dbus, avahi-daemon, and the server
RUN echo '#!/bin/bash\n\
mkdir -p /var/run/dbus\n\
dbus-daemon --system --fork\n\
avahi-daemon --daemonize --no-chroot\n\
sleep 2\n\
exec python3 mtls_server.py\n\
' > /start.sh && chmod +x /start.sh

# Run the server with Avahi support
CMD ["/start.sh"]
