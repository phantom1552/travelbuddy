#!/bin/bash

# AWS ECS Deployment Script for AI Trip Checklist API

set -euo pipefail

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
CLUSTER_NAME="ai-trip-checklist-cluster"
SERVICE_NAME="ai-trip-checklist-api"
TASK_FAMILY="ai-trip-checklist-api"
ECR_REPOSITORY="ai-trip-checklist-api"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured"
        exit 1
    fi
    
    # Get AWS account ID if not provided
    if [[ -z "$AWS_ACCOUNT_ID" ]]; then
        AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    fi
    
    success "Prerequisites check passed"
}

# Build and push Docker image
build_and_push_image() {
    log "Building and pushing Docker image..."
    
    local ecr_uri="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
    
    # Login to ECR
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ecr_uri"
    
    # Build image
    docker build -t "$ECR_REPOSITORY:$IMAGE_TAG" .
    
    # Tag for ECR
    docker tag "$ECR_REPOSITORY:$IMAGE_TAG" "$ecr_uri:$IMAGE_TAG"
    
    # Push to ECR
    docker push "$ecr_uri:$IMAGE_TAG"
    
    success "Image pushed to ECR: $ecr_uri:$IMAGE_TAG"
}

# Create or update ECS cluster
setup_cluster() {
    log "Setting up ECS cluster..."
    
    if aws ecs describe-clusters --clusters "$CLUSTER_NAME" --region "$AWS_REGION" &> /dev/null; then
        log "Cluster $CLUSTER_NAME already exists"
    else
        aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION"
        success "Cluster $CLUSTER_NAME created"
    fi
}

# Register task definition
register_task_definition() {
    log "Registering task definition..."
    
    # Update task definition with current values
    local task_def_file="cloud-deploy/aws-ecs/task-definition.json"
    local temp_file=$(mktemp)
    
    sed -e "s/ACCOUNT_ID/$AWS_ACCOUNT_ID/g" \
        -e "s/REGION/$AWS_REGION/g" \
        "$task_def_file" > "$temp_file"
    
    # Register task definition
    local task_def_arn=$(aws ecs register-task-definition \
        --cli-input-json "file://$temp_file" \
        --region "$AWS_REGION" \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    rm "$temp_file"
    
    success "Task definition registered: $task_def_arn"
    echo "$task_def_arn"
}

# Create or update ECS service
deploy_service() {
    local task_def_arn="$1"
    
    log "Deploying ECS service..."
    
    if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --region "$AWS_REGION" | grep -q "ACTIVE"; then
        # Update existing service
        aws ecs update-service \
            --cluster "$CLUSTER_NAME" \
            --service "$SERVICE_NAME" \
            --task-definition "$task_def_arn" \
            --region "$AWS_REGION" > /dev/null
        
        success "Service $SERVICE_NAME updated"
    else
        # Create new service
        local service_def_file="cloud-deploy/aws-ecs/service-definition.json"
        local temp_file=$(mktemp)
        
        # Get the revision number from task definition ARN
        local revision=$(echo "$task_def_arn" | sed 's/.*://')
        
        sed -e "s/REVISION/$revision/g" \
            -e "s/REGION/$AWS_REGION/g" \
            -e "s/ACCOUNT_ID/$AWS_ACCOUNT_ID/g" \
            "$service_def_file" > "$temp_file"
        
        aws ecs create-service \
            --cli-input-json "file://$temp_file" \
            --region "$AWS_REGION" > /dev/null
        
        rm "$temp_file"
        
        success "Service $SERVICE_NAME created"
    fi
}

# Wait for deployment to complete
wait_for_deployment() {
    log "Waiting for deployment to complete..."
    
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        local running_count=$(aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$AWS_REGION" \
            --query 'services[0].runningCount' \
            --output text)
        
        local desired_count=$(aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$AWS_REGION" \
            --query 'services[0].desiredCount' \
            --output text)
        
        if [[ "$running_count" == "$desired_count" ]]; then
            success "Deployment completed successfully"
            break
        fi
        
        if [[ $attempt -eq $max_attempts ]]; then
            error "Deployment timed out"
            exit 1
        fi
        
        log "Attempt $attempt/$max_attempts - Running: $running_count, Desired: $desired_count"
        sleep 30
        ((attempt++))
    done
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Get service details
    local service_info=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$SERVICE_NAME" \
        --region "$AWS_REGION")
    
    local service_status=$(echo "$service_info" | jq -r '.services[0].status')
    local running_count=$(echo "$service_info" | jq -r '.services[0].runningCount')
    local desired_count=$(echo "$service_info" | jq -r '.services[0].desiredCount')
    
    log "Service Status: $service_status"
    log "Running Tasks: $running_count/$desired_count"
    
    if [[ "$service_status" == "ACTIVE" && "$running_count" == "$desired_count" ]]; then
        success "Deployment verification passed"
    else
        error "Deployment verification failed"
        exit 1
    fi
}

# Main deployment function
main() {
    log "Starting AWS ECS deployment..."
    
    check_prerequisites
    build_and_push_image
    setup_cluster
    local task_def_arn=$(register_task_definition)
    deploy_service "$task_def_arn"
    wait_for_deployment
    verify_deployment
    
    success "AWS ECS deployment completed successfully!"
    log "Service: $SERVICE_NAME"
    log "Cluster: $CLUSTER_NAME"
    log "Region: $AWS_REGION"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "status")
        aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$AWS_REGION"
        ;;
    "logs")
        aws logs tail "/ecs/$TASK_FAMILY" --follow --region "$AWS_REGION"
        ;;
    "help")
        echo "Usage: $0 [deploy|status|logs|help]"
        echo ""
        echo "Commands:"
        echo "  deploy - Deploy the application (default)"
        echo "  status - Show service status"
        echo "  logs   - Show application logs"
        echo "  help   - Show this help message"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac