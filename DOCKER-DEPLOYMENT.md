# ThumbsUp Docker Deployment Guide

## Quick Start with Docker Compose

This is the easiest way to run both frontend and backend containers together.

### 1. Build and Run All Services

```bash
cd /path/to/thumbs-up
docker-compose up --build
```

This will:
- Build the frontend Docker image
- Build the backend Docker image
- Start both containers with proper networking
- Generate SSL certificates automatically
- Create persistent volumes for storage and certificates

### 2. Access the Services

**Frontend**: http://localhost:8080 (or your machine IP)
**Backend API**: https://localhost:8443 (HTTPS)

### 3. Configuration

Edit `docker-compose.yml` to change:
- `ADMIN_PIN=1234` - Change to your desired PIN
- `ENABLE_UPLOADS=true` - Set to false to disable uploads
- `ENABLE_DELETE=false` - Set to true to allow file deletion
- Port mappings (8080, 8443) - Change if conflicts exist

### 4. View Logs

```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### 5. Stop Services

```bash
docker-compose down
```

### 6. Access from Another Device

Find your host machine's IP (e.g., `192.168.1.100`):
- Frontend: http://192.168.1.100:8080
- Backend: https://192.168.1.100:8443

## Individual Container Build (if not using Compose)

### Build Backend

```bash
cd backend/apiv2
docker build -t thumbs-up-backend .
docker run -p 8443:8443 -e ADMIN_PIN=1234 thumbs-up-backend
```

### Build Frontend

```bash
cd frontend
docker build -t thumbs-up-frontend .
docker run -p 8080:8080 thumbs-up-frontend
```

## What Each Container Does

### Frontend Container
- Serves static files or Flask app on port 8080
- Generates self-signed certificates (optional for frontend)
- Accessible from browser or other devices

### Backend Container
- Runs Flask API server on port 8443 (HTTPS)
- Generates self-signed SSL certificates automatically
- Manages file storage and guest tokens
- Requires ADMIN_PIN environment variable

## Certificates

Both containers automatically generate self-signed certificates on first run:
- Stored in `/app/certs/` inside containers
- Persisted via Docker volumes so they survive restarts
- Location: `certs/server_cert.pem` and `certs/server_key.pem`

## Environment Variables

### Backend (apiv2)
- `ADMIN_PIN` - Required for login (no default)
- `HOST` - Bind address (default: 0.0.0.0)
- `PORT` - Server port (default: 8443)
- `ENABLE_UPLOADS` - Allow file uploads (default: true)
- `ENABLE_DELETE` - Allow file deletion (default: false)
- `STORAGE_PATH` - Where to store files (default: ./storage)
- `TOKEN_EXPIRY_HOURS` - Token validity (default: 24)

### Frontend
- `SERVICE_NAME` - Display name (default: ThumbsUp File Share)

## Troubleshooting

### Port Already in Use
Change port mappings in `docker-compose.yml`:
```yaml
ports:
  - "9080:8080"  # Access via http://localhost:9080
  - "9443:8443"  # Access via https://localhost:9443
```

### Certificate Issues
Delete the volume and restart to regenerate:
```bash
docker-compose down -v  # Remove volumes
docker-compose up --build
```

### Check Container Status
```bash
docker-compose ps
```
