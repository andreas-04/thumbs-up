# ThumbsUp Backend

## Quick Start (Recommended)

The simplest way to start the server:

```bash
cd backend/apiv2
export ADMIN_PIN=1234  # Set your admin PIN
pip install -r requirements.txt  # Install dependencies
bash start_webserver.sh  # Start the server
```

On first run, the database will be automatically initialized with an admin user.
Visit `https://localhost:8443/admin/login` and use your PIN to login, then set your email and password.

## Manual Setup

### Setup python virtual environment

#### Activating

Linux/macOS
```bash
cd backend/apiv2
python3 --version # version must be 3+
python3 -m venv .venv # create the virtual env
source .venv/bin/activate # activate the virtual env
```
Windows
```bash
cd backend/apiv2
python --version # version must be 3+
python -m venv .venv # create the virtual env
.\.venv\Scripts\Activate.ps1 # activate the virtual env
```

#### Installing Dependencies

```bash
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Starting the Server

```bash
export ADMIN_PIN=your_pin_here
python3 -m core.server
# or
bash start_webserver.sh
```

## Authentication System

The new authentication system uses:
- **Email/password** for regular users
- **Admin PIN** for first-time admin login only
- **JWT tokens** for session management
- **SQLite database** for user storage

### First-Time Admin Setup

1. Start the server with `ADMIN_PIN` environment variable
2. Navigate to `/admin/login`
3. Enter your PIN
4. Set your admin email and new password
5. Future logins use email/password

### User Registration

Regular users can register at `/register` with email and password.

## Deprecated Features

- **startup.py** - Use direct server startup instead
- **SMB functionality** - Web interface only for now
- **QR code guest tokens** - Being refactored for user-specific access

## Development

### Installing New Dependencies

```bash
python3 -m pip install <package> 
# update dep list
pip freeze > requirements.txt
```