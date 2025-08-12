# Production Deployment Guide

This guide covers deploying the AI Trip Checklist API to production environments.

## Prerequisites

### System Requirements
- Docker 20.10+ and Docker Compose 2.0+
- Minimum 2GB RAM, 1 CPU core
- 10GB available disk space
- Linux/Windows/macOS

### Required Services
- Groq API account and API key
- Domain name (for HTTPS)
- SSL certificates (recommended)

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd backend
   cp .env.production .env
   ```

2. **Configure Environment**
   Edit `.env` file with your production values:
   ```bash
   # Required
   GROQ_API_KEY=your-groq-api-key
   SECRET_KEY=your-super-secret-key
   ALLOWED_ORIGINS=https://yourdomain.com
   
   # Optional
   WORKERS=4
   LOG_LEVEL=INFO
   ```

3. **Deploy**
   ```bash
   # Linux/macOS
   ./scripts/deploy.sh
   
   # Windows
   .\scripts\deploy.ps1
   ```

4. **Verify Deployment**
   ```bash
   curl http://localhost:8000/health
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | Yes | production | Environment name |
| `DEBUG` | No | false | Enable debug mode |
| `GROQ_API_KEY` | Yes | - | Groq API key |
| `SECRET_KEY` | Yes | - | JWT secret key |
| `ALLOWED_ORIGINS` | Yes | - | CORS allowed origins |
| `WORKERS` | No | 4 | Number of worker processes |
| `LOG_LEVEL` | No | INFO | Logging level |
| `RATE_LIMIT_REQUESTS` | No | 100 | Requests per window |
| `RATE_LIMIT_WINDOW` | No | 60 | Rate limit window (seconds) |

### Security Configuration

The application includes several security features:

- **Rate Limiting**: Prevents abuse with configurable limits
- **Security Headers**: HSTS, CSP, X-Frame-Options, etc.
- **Input Validation**: Request size limits and sanitization
- **CORS**: Configurable cross-origin resource sharing
- **Authentication**: JWT-based authentication system

### SSL/HTTPS Setup

For production, HTTPS is strongly recommended:

1. **Obtain SSL Certificates**
   ```bash
   # Using Let's Encrypt (example)
   certbot certonly --standalone -d yourdomain.com
   ```

2. **Configure Nginx**
   Update `nginx.conf` to enable HTTPS section and update paths:
   ```nginx
   ssl_certificate /path/to/your/certificate.crt;
   ssl_certificate_key /path/to/your/private.key;
   ```

3. **Update Environment**
   ```bash
   ALLOWED_ORIGINS=https://yourdomain.com
   ```

## Deployment Options

### Option 1: Docker Compose (Recommended)

Simple deployment with Docker Compose:

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down
```

### Option 2: Manual Docker

For custom setups:

```bash
# Build image
docker build -t ai-trip-checklist-api .

# Run container
docker run -d \
  --name ai-trip-checklist-api \
  -p 8000:8000 \
  --env-file .env \
  ai-trip-checklist-api
```

### Option 3: Cloud Deployment

#### AWS ECS
1. Push image to ECR
2. Create ECS task definition
3. Deploy to ECS service

#### Google Cloud Run
1. Push image to GCR
2. Deploy to Cloud Run
3. Configure custom domain

#### Azure Container Instances
1. Push image to ACR
2. Create container instance
3. Configure networking

## Monitoring and Logging

### Health Checks

The application provides multiple health check endpoints:

- `/health` - Comprehensive health status
- `/health/live` - Simple liveness check
- `/health/ready` - Readiness check for orchestration

### Logging

Logs are structured and include:
- Request/response logging
- Error tracking
- Performance metrics
- Business events

Configure logging with:
```bash
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log
```

### Monitoring Stack (Optional)

Enable monitoring with Prometheus and Grafana:

```bash
# Start with monitoring
docker-compose -f docker-compose.prod.yml --profile monitoring up -d

# Access Grafana
open http://localhost:3000
```

## Performance Optimization

### Resource Limits

Configure appropriate resource limits:

```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.25'
```

### Worker Configuration

Adjust workers based on your server:

```bash
# Formula: (2 x CPU cores) + 1
WORKERS=4  # For 2 CPU cores
```

### Database Connection Pooling

When using a database:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db?pool_size=20&max_overflow=0
```

## Security Best Practices

### 1. Environment Security
- Use strong, unique `SECRET_KEY`
- Rotate API keys regularly
- Limit CORS origins to your domains only
- Use HTTPS in production

### 2. Network Security
- Use reverse proxy (Nginx)
- Configure firewall rules
- Enable rate limiting
- Monitor for suspicious activity

### 3. Container Security
- Run as non-root user
- Use minimal base images
- Scan images for vulnerabilities
- Keep dependencies updated

### 4. Data Security
- Encrypt sensitive data at rest
- Use secure communication channels
- Implement proper access controls
- Regular security audits

## Backup and Recovery

### Automated Backups

The deployment script creates automatic backups:

```bash
# Manual backup
./scripts/deploy.sh backup

# Restore from backup
./scripts/deploy.sh rollback
```

### Data Backup Strategy

1. **Configuration**: Environment files, certificates
2. **Application Data**: User data, logs
3. **Container Images**: Tagged and versioned

### Disaster Recovery

1. **Regular Backups**: Automated daily backups
2. **Multi-Region**: Deploy to multiple regions
3. **Monitoring**: Alert on failures
4. **Documentation**: Recovery procedures

## Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Check configuration
docker-compose -f docker-compose.prod.yml config
```

#### 2. Health Check Failures
```bash
# Test health endpoint
curl -v http://localhost:8000/health

# Check Groq API connectivity
curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
```

#### 3. High Memory Usage
```bash
# Monitor resources
docker stats

# Adjust worker count
WORKERS=2  # Reduce workers
```

#### 4. Rate Limiting Issues
```bash
# Adjust rate limits
RATE_LIMIT_REQUESTS=200
RATE_LIMIT_WINDOW=60
```

### Debug Mode

For troubleshooting, temporarily enable debug mode:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

**Warning**: Never enable debug mode in production!

## Maintenance

### Regular Tasks

1. **Update Dependencies**
   ```bash
   # Update base image
   docker pull python:3.11-slim
   
   # Rebuild with latest packages
   docker-compose -f docker-compose.prod.yml build --no-cache
   ```

2. **Log Rotation**
   ```bash
   # Logs are automatically rotated
   # Manual cleanup if needed
   find logs/ -name "*.log.*" -mtime +30 -delete
   ```

3. **Security Updates**
   ```bash
   # Update system packages in container
   # Rebuild and redeploy regularly
   ```

### Scaling

#### Horizontal Scaling
```bash
# Scale API containers
docker-compose -f docker-compose.prod.yml up -d --scale api=3
```

#### Load Balancing
Configure Nginx upstream for multiple instances:

```nginx
upstream api_backend {
    server api_1:8000;
    server api_2:8000;
    server api_3:8000;
}
```

## Support

### Getting Help

1. Check logs first: `docker-compose logs`
2. Verify configuration: `docker-compose config`
3. Test health endpoints: `curl http://localhost:8000/health`
4. Review this documentation
5. Check GitHub issues

### Performance Monitoring

Monitor these key metrics:
- Response time < 500ms
- Error rate < 1%
- Memory usage < 80%
- CPU usage < 70%
- Disk usage < 80%

### Alerting

Set up alerts for:
- Service downtime
- High error rates
- Resource exhaustion
- Security events

## Changelog

### Version 1.0.0
- Initial production deployment
- Docker containerization
- Security hardening
- Monitoring integration
- Automated deployment scripts