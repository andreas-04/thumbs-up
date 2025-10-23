#!/usr/bin/env python3
"""
mTLS Server Example
Requires client certificate for authentication.
"""
import ssl
import socket
import subprocess
import time
from pathlib import Path

def broadcast_mdns(service_name, client_cn):
    """Broadcast mDNS announcement using avahi-publish"""
    try:
        # Use avahi-publish to broadcast the service
        # Format: avahi-publish -s "Service Name" _service._tcp PORT
        service_type = "_thumbsup._tcp"  # Custom service type for your app
        txt_record = f"client={client_cn},timestamp={int(time.time())}"
        
        # Run avahi-publish in the background
        # Using subprocess.Popen to not block the server
        cmd = [
            'avahi-publish', '-s',
            service_name,
            service_type,
            '8443',
            txt_record
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"  📡 Broadcasting mDNS: {service_name}.{service_type}")
        print(f"     TXT record: {txt_record}")
        
        return process
        
    except FileNotFoundError:
        print("  ⚠️  avahi-publish not found. Install avahi-utils for mDNS support.")
        return None
    except Exception as e:
        print(f"  ⚠️  mDNS broadcast error: {e}")
        return None

def run_mtls_server(host='0.0.0.0', port=8443):
    # Create SSL context for server
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Load server's certificate and private key
    context.load_cert_chain(
        certfile='../../pki/server_cert.pem',
        keyfile='../../pki/server_key.pem'
    )
    
    # Require client certificate (this is what makes it mTLS)
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Load the client certificate as a trusted CA
    # In production, you'd use a proper CA certificate
    context.load_verify_locations(cafile='../../pki/client_cert.pem')
    
    # Create socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(5)
        
        print(f"mTLS Server listening on {host}:{port}")
        print("Waiting for client connection with valid certificate...")
        
        with context.wrap_socket(sock, server_side=True) as ssock:
            while True:
                try:
                    conn, addr = ssock.accept()
                    print(f"\n✓ Client connected from {addr}")
                    
                    # Get client certificate info
                    cert = conn.getpeercert()
                    client_cn = "Unknown"
                    if cert:
                        subject = dict(x[0] for x in cert['subject'])
                        client_cn = subject.get('commonName', 'Unknown')
                        print(f"  Client CN: {client_cn}")
                        
                        # Broadcast mDNS announcement on successful connection
                        service_name = f"mTLS-Connection-{client_cn}"
                        mdns_process = broadcast_mdns(service_name, client_cn)
                    
                    # Handle client request
                    with conn:
                        data = conn.recv(1024)
                        if data:
                            message = data.decode('utf-8')
                            print(f"  Received: {message}")
                            
                            # Send response
                            response = f"Server received: {message}"
                            conn.sendall(response.encode('utf-8'))
                            print(f"  Sent: {response}")
                    
                    # Clean up mDNS process if it was started
                    if 'mdns_process' in locals() and mdns_process:
                        mdns_process.terminate()
                        print(f"  📡 Stopped mDNS broadcast for {client_cn}")
                
                except ssl.SSLError as e:
                    print(f"\n✗ SSL Error: {e}")
                    print("  Client certificate validation failed!")
                except KeyboardInterrupt:
                    print("\n\nShutting down server...")
                    break
                except Exception as e:
                    print(f"\n✗ Error: {e}")

if __name__ == '__main__':
    # Check if certificates exist
    required_files = ['../../pki/server_cert.pem', '../../pki/server_key.pem', '../../pki/client_cert.pem']
    missing = [f for f in required_files if not Path(f).exists()]
    
    if missing:
        print("Missing certificate files:", ', '.join(missing))
        print("\nPlease run: cd ../../pki && python gen_selfsigned.py")
    else:
        run_mtls_server()
