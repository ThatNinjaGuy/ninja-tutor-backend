# Update Backend CORS for Custom Domain

After you've configured your custom domain `reading.thatninjaguy.in`, update your backend to allow CORS requests from it.

## Step 1: Update Environment Variable

Run this command to add your custom domain to the allowed origins:

```bash
cd ninja_tutor_backend

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_HOSTING_URL="reading.thatninjaguy.in,ninja-tutor-44dec.web.app"
```

This will set the environment variable to include both domains (comma-separated).

## Step 2: Redeploy Backend

The backend code has been updated to support multiple domains, but you need to deploy the changes:

```bash
cd ninja_tutor_backend
gcloud builds submit --config cloudbuild.yaml
```

## Step 3: Verify

After deployment, check the logs to confirm both domains are added:

```bash
gcloud run services logs read ninja-tutor-backend --region us-central1 --limit 20 | grep "Added Firebase Hosting URLs"
```

You should see:

```
Added Firebase Hosting URLs to CORS: reading.thatninjaguy.in,ninja-tutor-44dec.web.app
```

## Step 4: Test

Test from both domains:

```bash
# Test from custom domain
curl -H "Origin: https://reading.thatninjaguy.in" \
  https://ninja-tutor-backend-764764156207.us-central1.run.app/health -i

# Should see: access-control-allow-origin: https://reading.thatninjaguy.in

# Test from default domain
curl -H "Origin: https://ninja-tutor-44dec.web.app" \
  https://ninja-tutor-backend-764764156207.us-central1.run.app/health -i

# Should see: access-control-allow-origin: https://ninja-tutor-44dec.web.app
```

## What Changed

The backend now supports:

- Multiple domains in `FIREBASE_HOSTING_URL` (comma-separated)
- Domains with or without `https://` prefix
- Both http and https variants for each domain

Example formats that work:

- `reading.thatninjaguy.in` (domain only)
- `https://reading.thatninjaguy.in` (with protocol)
- `reading.thatninjaguy.in,ninja-tutor-44dec.web.app` (multiple, comma-separated)


