#!/bin/bash

# AI Trip Checklist API Deployment Script
# This script handles production deployment with proper error handling and rollback

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/logs/deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker is not running"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if .env file exists
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        error ".env file not found. Please create it from .env.example"
        exit 1
    fi
    
    # Check if required environment variables are set
    source "$PROJECT_DIR/.env"
    if [[ -z "${GROQ_API_KEY:-}" ]]; then
        error "GROQ_API_KEY is not set in .env file"
        exit 1
    fi
    
    if [[ -z "${SECRET_KEY:-}" ]]; then
        error "SECRET_KEY is not set in .env file"
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Create necessary directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$PROJECT_DIR/ssl"
    
    success "Directories created"
}

# Backup current deployment
backup_current() {
    log "Creating backup of current deployment..."
    
    local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    mkdir -p "$backup_path"
    
    # Backup configuration files
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        cp "$PROJECT_DIR/.env" "$backup_path/"
    fi
    
    # Backup data directory
    if [[ -d "$PROJECT_DIR/data" ]]; then
        cp -r "$PROJECT_DIR/data" "$backup_path/"
    fi
    
    # Backup logs
    if [[ -d "$PROJECT_DIR/logs" ]]; then
        cp -r "$PROJECT_DIR/logs" "$backup_path/"
    fi
    
    echo "$backup_name" > "$PROJECT_DIR/.last_backup"
    success "Backup created: $backup_name"
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    cd "$PROJECT_DIR"
    
    # Build with no cache to ensure fresh build
    docker-compose -f docker-compose.prod.yml build --no-cache
    
    success "Docker images built successfully"
}

# Run tests
run_tests() {
    log "Running tests..."
    
    cd "$PROJECT_DIR"
    
    # Run tests in a temporary container
    if docker-compose -f docker-compose.prod.yml run --rm api python -m pytest tests/ -v; then
        success "All tests passed"
    else
        error "Tests failed"
        exit 1
    fi
}

# Deploy application
deploy() {
    log "Deploying application..."
    
    cd "$PROJECT_DIR"
    
    # Stop existing containers
    docker-compose -f docker-compose.prod.yml down
    
    # Start new containers
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost:8000/health/ready &> /dev/null; then
            success "Application is healthy and ready"
            break
        fi
        
        if [[ $attempt -eq $max_attempts ]]; then
            error "Application failed to become healthy within timeout"
            rollback
            exit 1
        fi
        
        log "Attempt $attempt/$max_attempts - waiting for application to be ready..."
        sleep 10
        ((attempt++))
    done
    
    success "Deployment completed successfully"
}

# Rollback to previous version
rollback() {
    error "Rolling back to previous version..."
    
    if [[ ! -f "$PROJECT_DIR/.last_backup" ]]; then
        error "No backup found for rollback"
        return 1
    fi
    
    local backup_name=$(cat "$PROJECT_DIR/.last_backup")
    local backup_path="$BACKUP_DIR/$backup_name"
    
    if [[ ! -d "$backup_path" ]]; then
        error "Backup directory not found: $backup_path"
        return 1
    fi
    
    # Stop current containers
    docker-compose -f docker-compose.prod.yml down
    
    # Restore backup
    if [[ -f "$backup_path/.env" ]]; then
        cp "$backup_path/.env" "$PROJECT_DIR/"
    fi
    
    if [[ -d "$backup_path/data" ]]; then
        rm -rf "$PROJECT_DIR/data"
        cp -r "$backup_path/data" "$PROJECT_DIR/"
    fi
    
    # Start containers with previous configuration
    docker-compose -f docker-compose.prod.yml up -d
    
    warning "Rollback completed"
}

# Cleanup old backups
cleanup_backups() {
    log "Cleaning up old backups..."
    
    # Keep only the last 5 backups
    cd "$BACKUP_DIR"
    ls -t | tail -n +6 | xargs -r rm -rf
    
    success "Old backups cleaned up"
}

# Show deployment status
show_status() {
    log "Deployment Status:"
    echo "===================="
    
    docker-compose -f docker-compose.prod.yml ps
    
    echo ""
    log "Application Health:"
    if curl -s http://localhost:8000/health | jq . 2>/dev/null; then
        success "Health check passed"
    else
        warning "Health check failed or jq not available"
        curl -s http://localhost:8000/health || echo "Health endpoint not responding"
    fi
}

# Main deployment function
main() {
    log "Starting deployment of AI Trip Checklist API"
    
    check_root
    check_prerequisites
    setup_directories
    backup_current
    build_images
    run_tests
    deploy
    cleanup_backups
    show_status
    
    success "Deployment completed successfully!"
    log "Application is running at http://localhost:8000"
    log "Health check: http://localhost:8000/health"
    log "API documentation: http://localhost:8000/docs (if enabled)"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "rollback")
        rollback
        ;;
    "status")
        show_status
        ;;
    "backup")
        backup_current
        ;;
    "help")
        echo "Usage: $0 [deploy|rollback|status|backup|help]"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy the application (default)"
        echo "  rollback - Rollback to previous version"
        echo "  status   - Show deployment status"
        echo "  backup   - Create backup of current deployment"
        echo "  help     - Show this help message"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac