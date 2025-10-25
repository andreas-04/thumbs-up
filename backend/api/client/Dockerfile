FROM ubuntu:22.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    nfs-common \
    avahi-daemon \
    avahi-utils \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy client application
COPY api/client/client.py /app/

# Copy PKI certificates
COPY pki/client_cert.pem /app/pki/client_cert.pem
COPY pki/client_key.pem /app/pki/client_key.pem
COPY pki/server_cert.pem /app/pki/server_cert.pem

# Copy startup script
COPY scripts/entrypoint_client.sh /app/start.sh
RUN chmod +x /app/start.sh

# Copy configuration files
COPY config/avahi-daemon.conf /etc/avahi/avahi-daemon.conf
COPY config/dbus-system.conf /etc/dbus-1/system.conf

# Create mount point for NFS
RUN mkdir -p /mnt/nas

# Default: Use mDNS discovery (no host specified)
# Override to skip discovery: docker run secure-nas-client /app/start.sh <host> <port>
CMD ["/app/start.sh"]
