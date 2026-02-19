# ThumbsUp - Deployment Guide

## Overview

ThumbsUp is a containerized file sharing application with a React frontend and Flask backend API. The system consists of two Docker containers:

- **Backend**: Flask REST API (Python) with SQLite database on port 8443 (HTTPS)
- **Frontend**: React SPA served by nginx on port 80 (HTTP)

## Architecture

```
┌─────────────────────────────────────────┐
│         Docker Compose                  │
│                                         │
│  ┌─────────────┐      ┌──────────────┐ │
│  │  Frontend   │      │   Backend    │ │
│  │  (nginx)    │─────▶│   (Flask)    │ │
│  │  Port 80    │ API  │   Port 8443  │ │
│  └─────────────┘      └──────────────┘ │
│                                         │
│  Shared Network: thumbsup-net           │
│  Volumes: storage, database, certs      │
└─────────────────────────────────────────┘
```

## Prerequisites

- Docker (v20.10+)
- Docker Compose (v2.0+)
- Git

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd thumbs-up
```

### 2. Set Environment Variables

Create a `.env` file in `backend/apiv2/`:

```bash
cp backend/apiv2/.env.example backend/apiv2/.env
```

Edit `.env` and set your admin PIN:

```env
ADMIN_PIN=your-secure-pin-here
CORS_ORIGINS=http://localhost,http://localhost:80
```

### 3. Build and Start Containers

```bash
cd backend/apiv2
docker-compose up --build -d
```

This will:
- Build both frontend and backend containers
- Create necessary volumes for persistence
- Start services on ports 80 (frontend) and 8443 (backend)
- Generate self-signed SSL certificates automatically

### 4. Access the Application

- **Frontend**: http://localhost
- **Backend API**: https://localhost:8443 (self-signed cert warning expected)

### 5. Initial Admin Setup

On first run, log in with your `ADMIN_PIN` to create the admin account.

## Environment Variables

### Backend (`backend/apiv2/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PIN` | *required* | Initial admin PIN for first-time setup |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8443` | HTTPS port |
| `TOKEN_EXPIRY_HOURS` | `24` | JWT token expiration time |
| `ENABLE_UPLOADS` | `true` | Allow file uploads |
| `ENABLE_DELETE` | `false` | Allow file deletion |
| `SERVICE_NAME` | `ThumbsUp File Share` | Service display name |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `DATABASE_URI` | `sqlite:///./data/thumbsup.db` | Database connection string |

### Frontend (`frontend/app/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `https://localhost:8443` | Backend API URL |

## REST API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login with email/password or PIN
- `POST /api/v1/auth/signup` - Register new user
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/refresh` - Refresh token

### System Settings (Admin Only)
- `GET /api/v1/settings` - Get system settings
- `PUT /api/v1/settings` - Update system settings

### User Management (Admin Only)
- `GET /api/v1/users` - List users (with search/pagination)
- `POST /api/v1/users` - Create user
- `GET /api/v1/users/:id` - Get user details
- `PUT /api/v1/users/:id` - Update user
- `DELETE /api/v1/users/:id` - Delete user

### Folder Permissions (Admin Only)
- `GET /api/v1/users/:id/permissions` - Get user permissions
- `PUT /api/v1/users/:id/permissions` - Update user permissions
- `GET /api/v1/folders` - List all folders

### File Operations
- `GET /api/v1/files?path=<path>` - List directory contents
- `POST /api/v1/files/upload` - Upload file
- `GET /api/v1/files/download?path=<path>` - Download file
- `POST /api/v1/files/mkdir` - Create directory
- `DELETE /api/v1/files?path=<path>` - Delete file/folder

### Dashboard (Admin Only)
- `GET /api/v1/stats/dashboard` - Get system statistics

## System Modes

### Open Mode (Default)
- Public file access (no authentication required)
- Anyone can browse and download files
- Uploads require authentication if enabled

### Protected Mode
- Authentication required for all file operations
- Folder-level permissions enforced
- Per-user access control lists (ACLs)

To switch modes, update via admin dashboard or API:

```bash
curl -X PUT https://localhost:8443/api/v1/settings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"mode": "protected"}'
```

## Volume Management

### Persistent Data

```yaml
volumes:
  thumbsup-db:       # SQLite database
    location: <docker-volume>
  
  ./storage:         # User uploaded files
    location: backend/apiv2/storage
```

### Backup

```bash
# Backup database
docker exec thumbsup-backend cp /app/data/thumbsup.db /app/storage/backup.db

# Backup files (already in ./storage on host)
tar -czf storage-backup.tar.gz backend/apiv2/storage/
```

### Restore

```bash
# Stop containers
docker-compose down

# Restore database
cp backup.db backend/apiv2/storage/thumbsup.db

# Restore files
tar -xzf storage-backup.tar.gz

# Restart
docker-compose up -d
```

## Development

### Run Backend Locally

```bash
cd backend/apiv2
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
export ADMIN_PIN=1234
python -m core.server
```

### Run Frontend Locally

```bash
cd frontend/app
npm install
npm run dev
```

Frontend will be available at http://localhost:5173

## Troubleshooting

### Frontend Can't Connect to Backend

1. Check CORS settings in backend `.env`:
   ```env
   CORS_ORIGINS=http://localhost,http://localhost:3000,http://localhost:5173
   ```

2. Verify backend is running:
   ```bash
   docker logs thumbsup-backend
   ```

3. Test API directly:
   ```bash
   curl -k https://localhost:8443/health
   ```

### Database Not Persisting

Check volume mount:
```bash
docker volume inspect apiv2_thumbsup-db
docker exec thumbsup-backend ls -la /app/data
```

### Self-Signed Certificate Warnings

This is expected. The backend auto-generates self-signed certificates. For production:

1. Use a reverse proxy (nginx/Caddy) with Let's Encrypt
2. Or provide your own certificates via environment variables:
   ```env
   CERT_PATH=/path/to/cert.pem
   KEY_PATH=/path/to/key.pem
   ```

### Port Conflicts

If ports 80 or 8443 are in use, modify `docker-compose.yml`:

```yaml
services:
  frontend:
    ports:
      - "8080:80"  # Change host port
  
  backend:
    ports:
      - "9443:8443"  # Change host port
```

Also update frontend `.env`:
```env
VITE_API_BASE_URL=https://localhost:9443
```

## Production Deployment

### Recommendations

1. **Use a Reverse Proxy**: Deploy nginx/Caddy in front for SSL termination
2. **Set Strong Admin PIN**: Change `ADMIN_PIN` to a secure value
3. **Restrict CORS**: Set specific origins in `CORS_ORIGINS`
4. **Enable Delete**: Only if needed: `ENABLE_DELETE=true`
5. **Regular Backups**: Automate database and storage backups
6. **Monitor Logs**: 
   ```bash
   docker-compose logs -f
   ```

### Sample Reverse Proxy (Caddy)

```caddyfile
thumbsup.example.com {
    reverse_proxy /api/* https://localhost:8443 {
        transport http {
            tls_insecure_skip_verify
        }
    }
    reverse_proxy /* http://localhost:80
}
```

## Updating

```bash
# Pull latest changes
git pull

# Rebuild and restart
cd backend/apiv2
docker-compose down
docker-compose up --build -d

# Check logs
docker-compose logs -f
```

## Uninstall

```bash
cd backend/apiv2
docker-compose down -v  # -v removes volumes (deletes all data!)
```

## Support

For issues, please check:
- Docker logs: `docker-compose logs`
- Backend logs: `docker logs thumbsup-backend`
- Frontend logs: `docker logs thumbsup-frontend`
- API health: `curl -k https://localhost:8443/health`

## License

See LICENSE file for details.
