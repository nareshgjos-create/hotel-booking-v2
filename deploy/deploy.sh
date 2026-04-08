#!/usr/bin/env bash
# deploy.sh — Build, push to ECR, and update ECS services
# Usage: AWS_ACCOUNT_ID=123456789012 AWS_REGION=eu-west-2 ./deploy/deploy.sh

set -euo pipefail

ACCOUNT="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
REGION="${AWS_REGION:-eu-west-2}"
ECR="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
CLUSTER="${ECS_CLUSTER:-hotel-booking}"

# ── 1. Authenticate Docker to ECR ─────────────────────────────────────────────
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR"

# ── 2. Build images ────────────────────────────────────────────────────────────
docker build -f Dockerfile.backend  -t hotel-booking/backend:latest  .
docker build -f Dockerfile.frontend -t hotel-booking/frontend:latest .

# ── 3. Tag & push ──────────────────────────────────────────────────────────────
for svc in backend frontend; do
  docker tag  "hotel-booking/${svc}:latest" "${ECR}/hotel-booking/${svc}:latest"
  docker push "${ECR}/hotel-booking/${svc}:latest"
done

# ── 4. Register updated task definitions ──────────────────────────────────────
# Substitute ACCOUNT_ID and REGION placeholders before registering
for svc in backend frontend; do
  sed -e "s/ACCOUNT_ID/${ACCOUNT}/g" \
      -e "s/REGION/${REGION}/g" \
      "deploy/ecs-task-${svc}.json" \
    | aws ecs register-task-definition --region "$REGION" --cli-input-json file:///dev/stdin
done

# ── 5. Update ECS services to use the new task revision ───────────────────────
for svc in backend frontend; do
  aws ecs update-service \
    --region "$REGION" \
    --cluster "$CLUSTER" \
    --service "hotel-booking-${svc}" \
    --task-definition "hotel-booking-${svc}" \
    --force-new-deployment
done

echo "✅ Deployment triggered. Monitor at:"
echo "   https://${REGION}.console.aws.amazon.com/ecs/v2/clusters/${CLUSTER}/services"
