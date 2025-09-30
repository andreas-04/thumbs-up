# api/main.py
from fastapi import FastAPI, Header, HTTPException
import subprocess, os
from cert_checks import verify_client_attributes

app = FastAPI()

@app.post("/activate")
async def activate(x_client_cert: str = Header(None)):
    # x_client_cert is expected to be provided by the TLS terminator (nginx/stunnel) as a header.
    if not x_client_cert:
        raise HTTPException(401, "Client certificate required")
    attrs_ok = verify_client_attributes(x_client_cert, required=["role:owner"])
    if not attrs_ok:
        raise HTTPException(403, "certificate attributes not allowed")
    # start services (example)
    subprocess.run(["systemctl","start","secure-drive-nfs.service"], check=True)
    subprocess.run(["/usr/local/bin/unlock_luks.py"], check=True)  # must be careful with privileges
    return {"status":"activated"}
