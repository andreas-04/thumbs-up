# Use Ubuntu as base image
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and dependencies
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the client script from example/client/
COPY example/client/mtls_client.py .

# Copy certificates from pki directory
COPY pki/client_cert.pem ./client_cert.pem
COPY pki/client_key.pem ./client_key.pem
COPY pki/server_cert.pem ./server_cert.pem

# Update the certificate paths in the script to use current directory
RUN sed -i "s|certfile='../../pki/client_cert.pem'|certfile='./client_cert.pem'|g" mtls_client.py && \
    sed -i "s|keyfile='../../pki/client_key.pem'|keyfile='./client_key.pem'|g" mtls_client.py && \
    sed -i "s|cafile='../../pki/server_cert.pem'|cafile='./server_cert.pem'|g" mtls_client.py && \
    sed -i "s|'../../pki/client_cert.pem'|'./client_cert.pem'|g" mtls_client.py && \
    sed -i "s|'../../pki/client_key.pem'|'./client_key.pem'|g" mtls_client.py && \
    sed -i "s|'../../pki/server_cert.pem'|'./server_cert.pem'|g" mtls_client.py

# Run the client (can be overridden with docker run command)
CMD ["python3", "mtls_client.py"]
