# Robust Data Processor

A scalable, event-driven log processing pipeline built on Google Cloud Platform.

## Overview

This system ingests logs from multiple tenants at high volume, processes them asynchronously, and stores them with strict multi-tenant isolation. The architecture is designed to handle 1,000+ requests per minute while maintaining sub-100ms API response times.

## Architecture
```
User Request → FastAPI API → Cloud Pub/Sub → Worker Service → Firestore
                (Cloud Run)    (Queue)        (Cloud Run)      (NoSQL DB)
```

### Components

**API Service** (`api/`)
- Receives logs in JSON and plain text formats
- Validates and normalizes input data
- Publishes messages to Pub/Sub immediately
- Returns 202 Accepted without blocking (< 100ms response time)

**Message Queue** (Cloud Pub/Sub)
- Buffers messages between API and worker
- Provides automatic retry logic on failure
- Guarantees at-least-once delivery

**Worker Service** (`worker/`)
- Subscribes to Pub/Sub via HTTP push
- Simulates heavy processing (0.05 seconds per character)
- Transforms data (e.g., redacts sensitive information)
  - This can be anything that takes time for the assignment
- Saves to Firestore with tenants being isolated

**Database** (Firestore)
- Stores processed logs with strict tenant separation
- Native mode for hierarchical data structure
- Automatic scaling and high availability

## Multi-Tenant Isolation

Each tenant's data is physically separated using Firestore's hierarchical structure:
```
tenants/
  {tenant_id}/
    processed_logs/
      {log_id}/
        - source
        - original_text
        - modified_data
        - processed_at
        - processing_time_seconds
```

This structure ensures that queries for one tenant cannot accidentally access another tenant's data. The isolation is enforced at the database structure level, not just in application code.

## Features

- Non-blocking async API (returns 202 immediately)
- Handles 1,000+ requests per minute
- Automatic crash recovery via Pub/Sub retry
- Multi-tenant data isolation
- Serverless auto-scaling (scales to zero when idle)
- CI/CD with GitHub Actions
- Comprehensive error handling

## API Endpoints

### POST /ingest

Ingests log entries in JSON or plain text format.

**JSON Format:**
```bash
curl -X POST https://THE-API-URL/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme_corp",
    "log_id": "log-001",
    "text": "Log entry text"
  }'
```



**Plain Text Format:**
```bash
curl -X POST https://THE-API-URL/ingest \
  -H "Content-Type: text/plain" \
  -H "X-Tenant-ID: acme_corp" \
  -d "Log entry text"
```

**Response:**
```json
{
  "status": "accepted",
  "log_id": "log-001"
}
```

Status Code: `202 Accepted`

### GET /health

Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "ok"
}
```

Status Code: `200 OK`

## Data Flow

1. User sends POST request to `/ingest` endpoint
2. API validates input and publishes message to Pub/Sub topic
3. API returns 202 Accepted immediately (0.1 seconds)
4. Pub/Sub automatically pushes message to worker via HTTP
5. Worker processes message (simulates heavy work: 0.05s per character)
6. Worker transforms data (e.g., redacts phone numbers)
7. Worker saves to Firestore with tenant isolation
8. Worker acknowledges message to Pub/Sub (200 OK)
9. Pub/Sub deletes message from queue

## Crash Recovery

The system is resilient to failures:

- If the worker crashes during processing, the message remains in Pub/Sub
- Pub/Sub automatically retries after the acknowledgment deadline (600 seconds)
- New worker instance processes the message
- Zero data loss is guaranteed

## Deployment

### Prerequisites

- Google Cloud Platform account
- gcloud CLI installed and configured
- Project with billing enabled

### Required APIs

Enable the following APIs in your GCP project:
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  pubsub.googleapis.com \
  firestore.googleapis.com
```

### Manual Deployment

**Deploy API:**
```bash
cd api
gcloud run deploy log-ingest-api \
  --source . \
  --region us-east4 \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=your-project-id,ENVIRONMENT=production
```

**Deploy Worker:**
```bash
cd worker
gcloud run deploy log-processor-worker \
  --source . \
  --region us-east4 \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=your-project-id,ENVIRONMENT=production
```

**Create Pub/Sub Topic:**
```bash
gcloud pubsub topics create log-ingestion
```

**Create Pub/Sub Subscription:**
```bash
gcloud pubsub subscriptions create log-ingestion-sub \
  --topic=log-ingestion \
  --push-endpoint=https://your-worker-url/process \
  --ack-deadline=600
```

**Create Firestore Database:**
1. Navigate to Firestore in GCP Console
2. Create database in Native mode
3. Choose region: us-east4 for this project

### CI/CD Deployment

The project includes GitHub Actions for automated deployment.

**Setup:**
1. Add GitHub Secrets:
   - `GCP_SA_KEY`: Base64-encoded service account JSON key
2. Add GitHub Variables:
   - `GCP_PROJECT_ID`: Your GCP project ID
   - `GCP_REGION`: Deployment region (e.g., us-east4)

**Automatic Deployment:**
- Push to `main` branch triggers deployment
- Workflow deploys API service
- Workflow runs integration tests
- Tests verify 202 status codes and endpoint health

## Local Development

### Setup
```bash
# Install dependencies
cd api
pip install -r requirements.txt

# Run API locally (development mode)
ENVIRONMENT=development uvicorn main:app --reload

# Test endpoints
curl http://localhost:8000/health
```

### Testing
```bash
# Test JSON ingestion
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "test", "log_id": "001", "text": "test log"}'

# Test plain text ingestion
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: text/plain" \
  -H "X-Tenant-ID: test" \
  -d "test log"

# Test error handling
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"log_id": "001", "text": "missing tenant"}'
```

## Load Testing

The system was tested at 1,000 requests per minute using Locust.

**Setup:**
```bash
pip install locust

# Run load test
locust -f locustfile.py \
  --host=https://your-api-url \
  --users=20 \
  --spawn-rate=2 \
  --run-time=2m \
  --headless
```

**Results:**
- 0% failure rate
- All requests returned 202 Accepted
- Average API response time: < 100ms
- No timeouts or errors
- System auto-scaled to handle load

## Project Structure
```
Robust-Data-Processor/
├── api/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile          # Container configuration
├── worker/
│   ├── worker.py           # Worker service
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile         # Container configuration
├── .github/
│   └── workflows/
│       └── deploy.yaml    # CI/CD pipeline
├── .gitignore
└── README.md
```

## Tech Stack

- **Language:** Python 3.11.5
- **API Framework:** FastAPI
- **Compute:** Google Cloud Run (serverless)
- **Message Queue:** Google Cloud Pub/Sub
- **Database:** Google Cloud Firestore (Native mode)
- **CI/CD:** GitHub Actions
- **Infrastructure:** Google Cloud Platform

## Error Handling

The API returns appropriate status codes for different error conditions:

- `202 Accepted`: Request successfully queued
- `400 Bad Request`: Missing required fields or invalid input
- `415 Unsupported Media Type`: Invalid Content-Type header
- `500 Internal Server Error`: Server-side processing error

## Security Considerations

- Multi-tenant data isolation at database structure level
- Service accounts with least-privilege access
- Sensitive data redaction in worker processing
- Environment-based configuration (development vs production)

## Future Enhancements

- Implement rate limiting per tenant
- Add dead letter queue for failed messages
- Create monitoring dashboard (Cloud Monitoring)
- Add GET endpoints to retrieve processed logs
- Implement log retention policies
- Add support for batch ingestion
- Create webhook notifications for processing completion

## Architecture Decisions

### Why Pub/Sub?

- Decouples API from processing logic
- Provides automatic retry and crash recovery
- Enables horizontal scaling of workers
- Guarantees at-least-once delivery

### Why Firestore?

- Hierarchical structure enables clean tenant isolation
- Automatic scaling and high availability
- Real-time capabilities for future features
- Strong consistency within a tenant's data

### Why Cloud Run?

- Serverless scaling (0 to 1000+ instances)
- Pay only for actual request processing
- Built-in HTTPS endpoints
- Container-based deployment flexibility

### Why Sub-collections for Tenants?

- Physical data separation at storage level
- Impossible to accidentally query across tenants
- Scalable per-tenant data growth
- Clear compliance and audit trail

## Contact

Sasmit Munagala
- GitHub: https://github.com/SasmitM
- Project Repository: https://github.com/SasmitM/Robust-Data-Processor