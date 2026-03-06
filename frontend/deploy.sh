#!/bin/bash

# Contact API Frontend Deployment Script
set -e

echo "🚀 Starting Contact API Frontend Deployment..."

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"cobalt-howl-278500"}
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"contact-api-frontend"}
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"
BUILD_TAG=${BUILD_TAG:-$(date +%Y%m%d-%H%M%S)}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker."
    exit 1
fi

print_status "Prerequisites check passed"

# Set project
echo "📝 Setting up Google Cloud project..."
gcloud config set project $PROJECT_ID
print_status "Project set to $PROJECT_ID"

# Enable APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
print_status "APIs enabled"

# Build and push container
echo "🏗️ Building container image..."
docker build -t $IMAGE_NAME:$BUILD_TAG .
docker tag $IMAGE_NAME:$BUILD_TAG $IMAGE_NAME:latest

echo "📦 Pushing container to registry..."
docker push $IMAGE_NAME:$BUILD_TAG
docker push $IMAGE_NAME:latest
print_status "Container pushed to $IMAGE_NAME:$BUILD_TAG"

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME:$BUILD_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 80 \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars "REACT_APP_API_URL=${REACT_APP_API_URL:-https://contact-api-backend-url.com}" \
    --set-env-vars "REACT_APP_FIREBASE_API_KEY=${REACT_APP_FIREBASE_API_KEY}" \
    --set-env-vars "REACT_APP_FIREBASE_AUTH_DOMAIN=${REACT_APP_FIREBASE_AUTH_DOMAIN}" \
    --set-env-vars "REACT_APP_FIREBASE_PROJECT_ID=${REACT_APP_FIREBASE_PROJECT_ID}" \
    --set-env-vars "REACT_APP_FIREBASE_STORAGE_BUCKET=${REACT_APP_FIREBASE_STORAGE_BUCKET}" \
    --set-env-vars "REACT_APP_FIREBASE_MESSAGING_SENDER_ID=${REACT_APP_FIREBASE_MESSAGING_SENDER_ID}" \
    --set-env-vars "REACT_APP_FIREBASE_APP_ID=${REACT_APP_FIREBASE_APP_ID}"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

print_status "Deployment completed successfully!"
echo ""
echo "🌐 Service URL: $SERVICE_URL"
echo "📊 Dashboard: $SERVICE_URL"
echo "🔍 Search: $SERVICE_URL"
echo "⚙️ Admin: $SERVICE_URL"
echo ""
echo "🔧 To update environment variables:"
echo "gcloud run services update $SERVICE_NAME --region $REGION --set-env-vars KEY=VALUE"
echo ""
echo "📋 To view logs:"
echo "gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\" --limit 50 --format=\"table(timestamp,textPayload)\""
echo ""
echo "✨ Deployment complete!"