FROM ubuntu:22.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    avahi-daemon \
    avahi-utils \
    dbus \
    nfs-kernel-server \
    iptables \
    cryptsetup \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy server application modules
COPY api/server/*.py /app/
COPY api/server/pkg/ /app/pkg/

# Copy PKI certificates
COPY pki/server_cert.pem /app/pki/server_cert.pem
COPY pki/server_key.pem /app/pki/server_key.pem
COPY pki/client_cert.pem /app/pki/client_cert.pem

# Copy startup script
COPY api/server/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy configuration files
COPY config/avahi-daemon.conf /etc/avahi/avahi-daemon.conf
COPY config/dbus-system.conf /etc/dbus-1/system.conf

# Create directories for storage simulation
RUN mkdir -p /mnt/encrypted_storage /app/demo_storage

# Copy demo data files to a staging location (will be copied to volume on startup)
COPY api/server/demo_luks/ /app/demo_data_template/

# Expose mTLS port, NFS port, and RPC ports
EXPOSE 8443
EXPOSE 2049
EXPOSE 111
EXPOSE 111/udp
EXPOSE 20048

# Use the startup script as entrypoint
CMD ["/app/entrypoint.sh"]
