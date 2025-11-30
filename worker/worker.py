from fastapi import FastAPI, Request, HTTPException
from google.cloud import firestore
import json
import base64
import time
import os

app = FastAPI(title="Log Processor Worker")

# Initialize Firestore
db = firestore.Client()

@app.get("/")
def root():
    return {
        "status": "healthy",
        "service": "log-processor-worker",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process")
async def process(request: Request):
    """
    Receives messages from Pub/Sub push subscription
    """
    try:
        # Parse Pub/Sub message envelope
        envelope = await request.json()
        
        if "message" not in envelope:
            raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")
        
        # Decode base64 message data
        message_data = base64.b64decode(envelope["message"]["data"])
        data = json.loads(message_data)
        
        tenant_id = data.get("tenant_id")
        log_id = data.get("log_id")
        text = data.get("text")
        source = data.get("source", "unknown")
        
        # Validate required fields
        if not tenant_id or not log_id or not text:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Simulate heavy processing (0.05s per character)
        processing_time = len(text) * 0.05
        time.sleep(processing_time)
        
        # Do some processing (e.g., redact phone numbers)
        modified_text = text.replace("555-", "[REDACTED]-")
        
        # Save to Firestore with tenant isolation
        doc_ref = db.collection("tenants").document(tenant_id) \
                    .collection("processed_logs").document(log_id)
        
        doc_ref.set({
            "source": source,
            "original_text": text,
            "modified_data": modified_text,
            "processed_at": firestore.SERVER_TIMESTAMP,
            "processing_time_seconds": processing_time,
            "text_length": len(text)
        })
        
        print(f"✅ Processed log {log_id} for tenant {tenant_id} ({len(text)} chars, {processing_time:.2f}s)")
        
        # Return 200 = acknowledge message to Pub/Sub
        return {
            "status": "processed",
            "log_id": log_id,
            "tenant_id": tenant_id,
            "processing_time": processing_time
        }, 200
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON in message")
    except Exception as e:
        print(f"❌ Processing error: {e}")
        # Return 500 so Pub/Sub will retry
        raise HTTPException(status_code=500, detail=str(e))
