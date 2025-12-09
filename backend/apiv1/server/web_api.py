#!/usr/bin/env python3
"""
Web API for browser-based clients
Provides HTTP/WebSocket interface for file access without client installation
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from aiohttp import web
import aiohttp_cors
import jwt
import secrets

logger = logging.getLogger(__name__)


@dataclass
class WebSession:
    """Represents a web client session."""
    session_id: str
    ip: str
    user_agent: str
    connected_at: datetime
    last_activity: datetime


class WebAPI:
    """
    Web-based API for ThumbsUp NAS access.
    
    Provides:
    - Session-based authentication (JWT tokens)
    - File browsing and download via REST API
    - QR code generation for easy access
    - WebSocket for real-time updates
    """
    
    def __init__(self, storage_path: Path, port: int = 8080, secret_key: Optional[str] = None):
        self.storage_path = storage_path
        self.port = port
        self.secret_key = secret_key or secrets.token_hex(32)
        self.sessions: Dict[str, WebSession] = {}
        self.app = web.Application()
        self._setup_routes()
        self.runner: Optional[web.AppRunner] = None
        
    def _setup_routes(self):
        """Configure HTTP routes and CORS."""
        # Enable CORS for all routes
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
        
        # API routes
        routes = [
            web.get('/', self.handle_index),
            web.get('/api/status', self.handle_status),
            web.post('/api/auth/connect', self.handle_connect),
            web.get('/api/files', self.handle_list_files),
            web.get('/api/files/{path:.*}', self.handle_get_file),
            web.get('/api/qr', self.handle_qr_code),
            web.get('/ws', self.handle_websocket),
        ]
        
        for route in routes:
            cors.add(self.app.router.add_route(route.method, route.path, route.handler))
    
    async def handle_index(self, request: web.Request) -> web.Response:
        """Serve the web client interface."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>ThumbsUp NAS</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }
                .container {
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 800px;
                    width: 100%;
                    overflow: hidden;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }
                .header h1 { font-size: 2.5em; margin-bottom: 10px; }
                .header p { opacity: 0.9; }
                .content { padding: 30px; }
                .status {
                    background: #f0f4f8;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                }
                .status-indicator {
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    margin-right: 8px;
                }
                .status-indicator.online { background: #10b981; }
                .status-indicator.offline { background: #ef4444; }
                .btn {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 14px 28px;
                    border-radius: 8px;
                    font-size: 16px;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                    width: 100%;
                    margin: 10px 0;
                }
                .btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
                }
                .btn:active { transform: translateY(0); }
                .file-list {
                    list-style: none;
                    margin-top: 20px;
                }
                .file-item {
                    background: #f9fafb;
                    border: 1px solid #e5e7eb;
                    padding: 15px;
                    margin: 8px 0;
                    border-radius: 8px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    transition: background 0.2s;
                }
                .file-item:hover { background: #f3f4f6; }
                .file-name { font-weight: 500; color: #1f2937; }
                .file-size { color: #6b7280; font-size: 0.9em; }
                .download-btn {
                    background: #10b981;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                }
                .download-btn:hover { background: #059669; }
                #error {
                    background: #fee2e2;
                    color: #991b1b;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 10px 0;
                    display: none;
                }
                .qr-container {
                    text-align: center;
                    padding: 20px;
                    background: #f9fafb;
                    border-radius: 8px;
                    margin: 20px 0;
                }
                .qr-container img { max-width: 256px; margin: 20px auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>👍 ThumbsUp NAS</h1>
                    <p>Your files, your device, your network</p>
                </div>
                <div class="content">
                    <div class="status">
                        <span class="status-indicator online"></span>
                        <strong>Status:</strong> <span id="status">Connected</span>
                    </div>
                    
                    <button class="btn" onclick="connect()">Connect to NAS</button>
                    <button class="btn" onclick="listFiles()">Browse Files</button>
                    <button class="btn" onclick="showQR()">Show QR Code</button>
                    
                    <div id="error"></div>
                    <div id="qr-container" class="qr-container" style="display:none;"></div>
                    <ul id="fileList" class="file-list"></ul>
                </div>
            </div>
            
            <script>
                let token = null;
                
                function showError(msg) {
                    const el = document.getElementById('error');
                    el.textContent = msg;
                    el.style.display = 'block';
                    setTimeout(() => el.style.display = 'none', 5000);
                }
                
                async function connect() {
                    try {
                        const res = await fetch('/api/auth/connect', { method: 'POST' });
                        const data = await res.json();
                        token = data.token;
                        document.getElementById('status').textContent = 'Authenticated';
                        showError('✓ Connected successfully!');
                    } catch (e) {
                        showError('Connection failed: ' + e.message);
                    }
                }
                
                async function listFiles() {
                    if (!token) {
                        showError('Please connect first');
                        return;
                    }
                    
                    try {
                        const res = await fetch('/api/files', {
                            headers: { 'Authorization': 'Bearer ' + token }
                        });
                        const data = await res.json();
                        
                        const list = document.getElementById('fileList');
                        list.innerHTML = '';
                        
                        data.files.forEach(file => {
                            const li = document.createElement('li');
                            li.className = 'file-item';
                            li.innerHTML = `
                                <div>
                                    <div class="file-name">${file.name}</div>
                                    <div class="file-size">${formatSize(file.size)}</div>
                                </div>
                                <button class="download-btn" onclick="downloadFile('${file.path}')">
                                    Download
                                </button>
                            `;
                            list.appendChild(li);
                        });
                    } catch (e) {
                        showError('Failed to list files: ' + e.message);
                    }
                }
                
                async function downloadFile(path) {
                    if (!token) {
                        showError('Please connect first');
                        return;
                    }
                    
                    window.location.href = `/api/files/${path}?token=${token}`;
                }
                
                async function showQR() {
                    const container = document.getElementById('qr-container');
                    const url = window.location.origin;
                    container.innerHTML = `
                        <h3>Scan to Access</h3>
                        <img src="/api/qr?url=${encodeURIComponent(url)}" alt="QR Code">
                        <p>Share this QR code to give others access</p>
                    `;
                    container.style.display = 'block';
                }
                
                function formatSize(bytes) {
                    if (bytes < 1024) return bytes + ' B';
                    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
                    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
                }
                
                // Auto-connect on load
                connect();
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def handle_status(self, request: web.Request) -> web.Response:
        """Get server status."""
        status = {
            'status': 'online',
            'active_sessions': len(self.sessions),
            'storage_available': True,
            'timestamp': datetime.now().isoformat()
        }
        return web.json_response(status)
    
    async def handle_connect(self, request: web.Request) -> web.Response:
        """Create a new session and return JWT token."""
        client_ip = request.remote
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Create session
        session_id = secrets.token_urlsafe(32)
        session = WebSession(
            session_id=session_id,
            ip=client_ip,
            user_agent=user_agent,
            connected_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        self.sessions[session_id] = session
        logger.info(f"[Web] New session from {client_ip}")
        
        # Generate JWT token
        token = jwt.encode({
            'session_id': session_id,
            'ip': client_ip,
            'exp': datetime.now().timestamp() + 3600  # 1 hour expiry
        }, self.secret_key, algorithm='HS256')
        
        return web.json_response({
            'token': token,
            'session_id': session_id,
            'expires_in': 3600
        })
    
    def _verify_token(self, request: web.Request) -> Optional[str]:
        """Verify JWT token and return session_id."""
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            session_id = payload.get('session_id')
            
            # Update last activity
            if session := self.sessions.get(session_id):
                session.last_activity = datetime.now()
                return session_id
        except jwt.InvalidTokenError:
            pass
        
        return None
    
    async def handle_list_files(self, request: web.Request) -> web.Response:
        """List files in storage."""
        if not self._verify_token(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        try:
            files = []
            for item in self.storage_path.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(self.storage_path)
                    files.append({
                        'name': item.name,
                        'path': str(rel_path),
                        'size': item.stat().st_size,
                        'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })
            
            return web.json_response({'files': files})
        except Exception as e:
            logger.error(f"[Web] Error listing files: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_get_file(self, request: web.Request) -> web.Response:
        """Download a file."""
        # Support token in query param for download links
        token_param = request.query.get('token')
        if token_param:
            try:
                payload = jwt.decode(token_param, self.secret_key, algorithms=['HS256'])
                session_id = payload.get('session_id')
                if not session_id or session_id not in self.sessions:
                    return web.json_response({'error': 'Invalid token'}, status=401)
            except jwt.InvalidTokenError:
                return web.json_response({'error': 'Invalid token'}, status=401)
        elif not self._verify_token(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        file_path = request.match_info.get('path', '')
        full_path = self.storage_path / file_path
        
        # Security: prevent directory traversal
        try:
            full_path = full_path.resolve()
            self.storage_path.resolve()
            if not str(full_path).startswith(str(self.storage_path.resolve())):
                return web.json_response({'error': 'Access denied'}, status=403)
        except Exception:
            return web.json_response({'error': 'Invalid path'}, status=400)
        
        if not full_path.exists() or not full_path.is_file():
            return web.json_response({'error': 'File not found'}, status=404)
        
        return web.FileResponse(full_path)
    
    async def handle_qr_code(self, request: web.Request) -> web.Response:
        """Generate QR code for easy access."""
        url = request.query.get('url', request.url.origin())
        
        try:
            import qrcode
            import io
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            
            return web.Response(body=buf.read(), content_type='image/png')
        except ImportError:
            # Fallback: return SVG QR code using simple text
            svg = f'''
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
                <rect width="200" height="200" fill="white"/>
                <text x="100" y="100" text-anchor="middle" font-size="12">
                    QR Code: {url}
                </text>
                <text x="100" y="120" text-anchor="middle" font-size="10">
                    (Install qrcode library for actual QR)
                </text>
            </svg>
            '''
            return web.Response(text=svg, content_type='image/svg+xml')
    
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket for real-time updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        logger.info(f"[Web] WebSocket connected from {request.remote}")
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    # Handle WebSocket messages
                    await ws.send_json({'type': 'pong', 'timestamp': datetime.now().isoformat()})
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"[Web] WebSocket error: {ws.exception()}")
        finally:
            logger.info(f"[Web] WebSocket disconnected from {request.remote}")
        
        return ws
    
    async def start(self):
        """Start the web server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"[Web] Server started on http://0.0.0.0:{self.port}")
    
    async def stop(self):
        """Stop the web server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("[Web] Server stopped")
