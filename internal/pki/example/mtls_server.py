#!/usr/bin/env python3
"""
mTLS Server Example
Requires client certificate for authentication.
"""
import ssl
import socket
from pathlib import Path

def run_mtls_server(host='localhost', port=8443):
    # Create SSL context for server
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Load server's certificate and private key
    context.load_cert_chain(
        certfile='../server_cert.pem',
        keyfile='../server_key.pem'
    )
    
    # Require client certificate (this is what makes it mTLS)
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Load the client certificate as a trusted CA
    # In production, you'd use a proper CA certificate
    context.load_verify_locations(cafile='../client_cert.pem')
    
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
                    if cert:
                        subject = dict(x[0] for x in cert['subject'])
                        print(f"  Client CN: {subject.get('commonName', 'Unknown')}")
                    
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
    required_files = ['../server_cert.pem', '../server_key.pem', '../client_cert.pem']
    missing = [f for f in required_files if not Path(f).exists()]
    
    if missing:
        print("Missing certificate files:", ', '.join(missing))
        print("\nPlease run: python gen_selfsigned.py")
    else:
        run_mtls_server()
