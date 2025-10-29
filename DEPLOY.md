# Backend Deployment Instructions

Quick deployment guide for the backend API.

## Prerequisites

1. Google Cloud SDK installed and authenticated
2. Project set to `ninja-tutor-44dec`
3. Environment variables configured

## Quick Deploy

```bash
# From the ninja_tutor_backend directory
gcloud builds submit --config cloudbuild.yaml
```

## Manual Deployment Steps

### 1. Build Docker Image

```bash
gcloud builds submit --tag gcr.io/ninja-tutor-44dec/ninja-tutor-backend
```

### 2. Deploy to Cloud Run

```bash
gcloud run deploy ninja-tutor-backend \
  --image gcr.io/ninja-tutor-44dec/ninja-tutor-backend \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1
```

### 3. Set Environment Variables

```bash
gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars FIREBASE_HOSTING_URL=ninja-tutor-44dec.web.app,DEBUG=false,LOG_LEVEL=INFO
```

### 4. Get Service URL

```bash
gcloud run services describe ninja-tutor-backend \
  --region us-central1 \
  --format='value(status.url)'
```

## Update Environment Variables

Use Google Secret Manager for sensitive credentials:

```bash
# Create secrets
echo -n "your-firebase-private-key" | gcloud secrets create firebase-private-key --data-file=-

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding firebase-private-key \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

## View Logs

```bash
gcloud run services logs read ninja-tutor-backend --region us-central1
```

## Rollback

```bash
gcloud run services update-traffic ninja-tutor-backend \
  --region us-central1 \
  --to-revisions=ninja-tutor-backend-00001-abc=100
```
