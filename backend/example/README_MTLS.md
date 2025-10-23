# mTLS (Mutual TLS) Example

This directory contains a complete example of mutual TLS authentication using self-signed certificates.

## What is mTLS?

Mutual TLS (mTLS) is a security protocol where **both** the client and server authenticate each other using certificates:
- **Regular TLS**: Only the server proves its identity to the client
- **mTLS**: Both server AND client prove their identities to each other

## Files

- `gen_selfsigned.py` - Generates self-signed certificates and keys
- `mtls_server.py` - Server that requires client certificate authentication
- `mtls_client.py` - Client that authenticates using its certificate

## Quick Start

### 1. Generate Certificates

```bash
python gen_selfsigned.py
```

This creates:
- `server_cert.pem` & `server_key.pem` - Server's identity
- `client_cert.pem` & `client_key.pem` - Client's identity

### 2. Start the Server

In one terminal:
```bash
python mtls_server.py
```

### 3. Run the Client

In another terminal:
```bash
python mtls_client.py
```

## How It Works

### Server Side (`mtls_server.py`)
1. Loads its own certificate (`server_cert.pem`) and private key (`server_key.pem`)
2. Sets `verify_mode = ssl.CERT_REQUIRED` to require client certificates
3. Trusts the client certificate by loading it as a CA
4. Only accepts connections from clients with valid certificates

### Client Side (`mtls_client.py`)
1. Loads its own certificate (`client_cert.pem`) and private key (`client_key.pem`)
2. Trusts the server certificate by loading it as a CA
3. Presents its certificate during TLS handshake
4. Only connects to servers with valid certificates

## Security Flow

```
Client                                    Server
  |                                         |
  |-------- TLS Handshake Start ----------->|
  |                                         |
  |<------- Server Certificate -------------|
  |         (server_cert.pem)              |
  |                                         |
  | Client verifies server cert            |
  | against server_cert.pem (trusted CA)   |
  |                                         |
  |-------- Client Certificate ------------>|
  |         (client_cert.pem)              |
  |                                         |
  |         Server verifies client cert     |
  |         against client_cert.pem (CA)    |
  |                                         |
  |<------- Handshake Complete -------------|
  |                                         |
  |======== Encrypted Communication ========|
```


## Testing Without Valid Client Certificate

Try this to see what happens when a client doesn't provide a certificate:

```bash
# This will fail with SSL error:
curl -k https://localhost:8443
```

The server will reject the connection because no client certificate was provided!

