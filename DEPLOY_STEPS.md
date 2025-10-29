# Step-by-Step Deployment

The app is failing because it needs environment variables (Firebase credentials) on first startup.

## Step 1: Deploy the Container

```bash
cd ninja_tutor_backend
gcloud builds submit --config cloudbuild.yaml
```

## Step 2: Set Environment Variables (Required!)

After the container deploys, you need to set the Firebase credentials and other environment variables:

```bash
# First, let's set basic config to prevent crash
gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars DEBUG=false,LOG_LEVEL=INFO,FIREBASE_HOSTING_URL=ninja-tutor-44dec.web.app

# Now set Firebase credentials using Secret Manager (Recommended)
# OR set them directly as environment variables:
gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_PROJECT_ID=ninja-tutor-44dec,\
    FIREBASE_CLIENT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com,\
    FIREBASE_CLIENT_ID=your-client-id,\
    FIREBASE_PRIVATE_KEY_ID=your-private-key-id,\
    FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_KEY\n-----END PRIVATE KEY-----\n",\
    OPENAI_API_KEY=your-openai-key
```

**OR use Secret Manager (more secure):**

```bash
# Create secrets
echo -n "your-firebase-project-id" | gcloud secrets create firebase-project-id --data-file=-
echo -n "your-firebase-client-email" | gcloud secrets create firebase-client-email --data-file=-
echo -n "your-firebase-client-id" | gcloud secrets create firebase-client-id --data-file=-
echo -n "your-firebase-private-key-id" | gcloud secrets create firebase-private-key-id --data-file=-
echo -n "your-firebase-private-key" | gcloud secrets create firebase-private-key --data-file=-
echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding firebase-project-id \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
# Repeat for other secrets

# Update Cloud Run to use secrets
gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-secrets FIREBASE_PROJECT_ID=firebase-project-id:latest
# Repeat for other secrets
```

## Step 3: Test the Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe ninja-tutor-backend \
  --region us-central1 \
  --format='value(status.url)')

echo "Service URL: $SERVICE_URL"

# Test health check
curl $SERVICE_URL/health

# View logs
gcloud run services logs read ninja-tutor-backend --region us-central1 --limit 50
```

## Alternative: Deploy with Env Vars in One Step

If you want to deploy with environment variables in one go, modify cloudbuild.yaml to add:

```yaml
- "--update-env-vars"
- "DEBUG=false,LOG_LEVEL=INFO"
```

But Firebase credentials should still be set via Secret Manager for security.
