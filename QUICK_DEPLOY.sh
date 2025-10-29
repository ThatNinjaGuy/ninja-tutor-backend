#!/bin/bash
# Quick Deployment Script for Ninja Tutor Backend
# Make this file executable: chmod +x QUICK_DEPLOY.sh

set -e

echo "🚀 Deploying Ninja Tutor Backend to Google Cloud Run..."
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if project is set
PROJECT=$(gcloud config get-value project)
echo "📋 Current project: $PROJECT"

# Confirm deployment
read -p "Deploy to this project? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 1
fi

# Build and deploy
echo "🔨 Building and deploying..."
gcloud builds submit --config cloudbuild.yaml

# Get the service URL
echo ""
echo "✅ Deployment complete!"
echo ""
echo "Service URL:"
gcloud run services describe ninja-tutor-backend \
  --region us-central1 \
  --format='value(status.url)'

echo ""
echo "📊 View logs:"
echo "gcloud run services logs read ninja-tutor-backend --region us-central1"

