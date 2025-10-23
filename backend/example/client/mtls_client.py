#!/usr/bin/env python3
"""
mTLS Client Example
Authenticates to server using client certificate.
"""
import ssl
import socket
from pathlib import Path

def run_mtls_client(host='localhost', port=8443, message='Hello from mTLS client!'):
    # Create SSL context for client
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    
    # Load client's certificate and private key for authentication
    context.load_cert_chain(
        certfile='../../pki/client_cert.pem',
        keyfile='../../pki/client_key.pem'
    )
    
    # Load server certificate as trusted CA
    # In production, you'd use a proper CA certificate
    context.load_verify_locations(cafile='../../pki/server_cert.pem')
    
    # For self-signed certs with "localhost", we need to set the server hostname
    context.check_hostname = False  # We're using self-signed cert
    
    # Create socket and connect
    with socket.create_connection((host, port)) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            print(f"✓ Connected to {host}:{port}")
            
            # Get server certificate info
            cert = ssock.getpeercert()
            if cert:
                subject = dict(x[0] for x in cert['subject'])
                print(f"  Server CN: {subject.get('commonName', 'Unknown')}")
            
            # Send message
            print(f"\nSending: {message}")
            ssock.sendall(message.encode('utf-8'))
            
            # Receive response
            data = ssock.recv(1024)
            response = data.decode('utf-8')
            print(f"Received: {response}")

if __name__ == '__main__':
    # Check if certificates exist
    required_files = ['../../pki/client_cert.pem', '../../pki/client_key.pem', '../../pki/server_cert.pem']
    missing = [f for f in required_files if not Path(f).exists()]
    
    if missing:
        print("Missing certificate files:", ', '.join(missing))
        print("\nPlease run: cd ../../pki && python gen_selfsigned.py")
    else:
        try:
            run_mtls_client()
        except ConnectionRefusedError:
            print("\n✗ Connection refused. Is the server running?")
            print("  Start server with: python mtls_server.py")
        except ssl.SSLError as e:
            print(f"\n✗ SSL Error: {e}")
        except Exception as e:
            print(f"\n✗ Error: {e}")
