# app.py
import os, re, datetime
from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient, ContentSettings

# Config (prefer connection string locally; App Service can use URL + managed identity if you want later)
CONN_STR        = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_URL     = os.getenv("STORAGE_ACCOUNT_URL", "https://yex8wbsystems.blob.core.windows.net")
IMAGES_CONTAINER= os.getenv("IMAGES_CONTAINER", "lanternfly-images")

# For simplicity: use connection string if present, else fall back to account URL + default creds (not shown)
if CONN_STR:
    bsc = BlobServiceClient.from_connection_string(CONN_STR)
else:
    from azure.identity import DefaultAzureCredential
    bsc = BlobServiceClient(account_url=STORAGE_URL, credential=DefaultAzureCredential())

cc  = bsc.get_container_client(IMAGES_CONTAINER)
try:
    cc.create_container()
except Exception:
    pass  # exists

app = Flask(__name__)

def sanitize(name: str) -> str:
    # keep simple and safe
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return safe or "upload.bin"

@app.post("/api/v1/upload")
def upload():
    if "file" not in request.files:
        return jsonify(ok=False, error="missing file"), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify(ok=False, error="empty filename"), 400

    # basic content-type gate
    if not (f.mimetype or "").startswith("image/"):
        return jsonify(ok=False, error="only image/* allowed"), 415

    ts   = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    name = f"{ts}-{sanitize(f.filename)}"
    bc   = bsc.get_blob_client(IMAGES_CONTAINER, name)

    bc.upload_blob(f.read(), overwrite=True,
                   content_settings=ContentSettings(content_type=f.mimetype))

    return jsonify(ok=True, url=f"{cc.url}/{name}")

@app.get("/api/v1/gallery")
def gallery():
    urls = [f"{cc.url}/{b.name}" for b in cc.list_blobs()]
    urls.sort(reverse=True)
    return jsonify(ok=True, gallery=urls)

@app.get("/api/v1/health")
def health():
    return "ok", 200

@app.get("/")
def index():
    return render_template("index.html")
