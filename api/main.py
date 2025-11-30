from fastapi import FastAPI, Request, Header, HTTPException
from google.cloud import pubsub_v1
import json
import uuid
import os

app = FastAPI(title="Log Ingestion API")

# Initialize Pub/Sub (will be configured later)
PROJECT_ID = os.getenv("PROJECT_ID", "sasmit-log-processor")
TOPIC_NAME = "log-ingestion"

# Only initialize publisher if not in local dev mode
if os.getenv("ENVIRONMENT") == "production":
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
else:
    publisher = None
    topic_path = None


@app.get("/")
def root():
    return {
        "status": "healthy",
        "service": "log-ingestion-api",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(request: Request, x_tenant_id: str = Header(None)):
    content_type = request.headers.get("content-type", "")

    # Handle JSON
    if "application/json" in content_type:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        tenant_id = data.get("tenant_id")
        log_id = data.get("log_id")
        text = data.get("text")
        source = "json"

    # Handle Plain Text
    elif "text/plain" in content_type:
        text_bytes = await request.body()
        text = text_bytes.decode("utf-8")
        tenant_id = x_tenant_id
        log_id = str(uuid.uuid4())
        source = "text_upload"

    else:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json or text/plain"
        )

    # Validation
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant_id")
    if not text or text.strip() == "":
        raise HTTPException(status_code=400, detail="Missing or empty text")

    # Create normalized message
    message = {
        "tenant_id": tenant_id,
        "log_id": log_id,
        "text": text,
        "source": source
    }

    # Publish to Pub/Sub (or simulate in dev mode)
    if publisher and topic_path:
        message_bytes = json.dumps(message).encode("utf-8")
        future = publisher.publish(topic_path, message_bytes)
        print(f"Published message: {future.result()}")
    else:
        # Local development mode - just log
        print(f"[DEV MODE] Would publish: tenant={tenant_id}, log_id={log_id}")

    return {"status": "accepted", "log_id": log_id}, 202