# PromptPlot v2.0 Deployment Guide

This guide covers production deployment strategies, performance optimization, and operational best practices for PromptPlot v2.0.

## Deployment Architecture

### Single Node Deployment
```
┌─────────────────────────────────────┐
│           Single Server             │
├─────────────────────────────────────┤
│  PromptPlot Application             │
│  ├─ CLI Interface                   │
│  ├─ Workflow Engine                 │
│  ├─ LLM Providers                   │
│  └─ Plotter Interface               │
├─────────────────────────────────────┤
│  Local Storage                      │
│  ├─ Configuration                   │
│  ├─ Cache                           │
│  └─ Results                         │
├─────────────────────────────────────┤
│  Hardware                           │
│  ├─ Serial Ports                    │
│  └─ Plotter Devices                 │
└─────────────────────────────────────┘
```

### Distributed Deployment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │  API Gateway    │    │  Load Balancer  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                            │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Workflow       │  LLM Service    │  Plotter Controller         │
│  Orchestrator   │  ├─ Azure AI    │  ├─ Device Manager          │
│  ├─ Queue       │  ├─ Ollama      │  ├─ Serial Interface        │
│  ├─ Scheduler   │  └─ Cache       │  └─ Status Monitor          │
│  └─ Monitor     │                 │                             │
└─────────────────┴─────────────────┴─────────────────────────────┘
         │                       │                       │
┌─────────────────┬─────────────────┬─────────────────────────────┤
│   Data Layer    │  Cache Layer    │  Hardware Layer             │
│  ├─ Config DB   │  ├─ Redis       │  ├─ Plotter Farm            │
│  ├─ Results DB  │  ├─ Memory      │  ├─ Camera Array            │
│  └─ Metrics DB  │  └─ Disk        │  └─ Sensor Network          │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Production Deployment

### Docker Deployment

#### Dockerfile
```dockerfile
# Multi-stage build for optimized production image
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build C extensions for performance
ENV PROMPTPLOT_BUILD_EXTENSIONS=1
COPY . /app
WORKDIR /app
RUN pip install -e .[performance]

# Production stage
FROM python:3.10-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    libudev1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application
COPY --from=builder /app /app
WORKDIR /app

# Create non-root user
RUN groupadd -r promptplot && useradd -r -g promptplot promptplot
RUN chown -R promptplot:promptplot /app

# Create directories
RUN mkdir -p /app/config /app/cache /app/results /app/logs
RUN chown -R promptplot:promptplot /app/config /app/cache /app/results /app/logs

USER promptplot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import promptplot; print('OK')" || exit 1

# Default command
CMD ["python", "-m", "promptplot.server"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  promptplot:
    build: .
    container_name: promptplot-app
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config:ro
      - ./cache:/app/cache
      - ./results:/app/results
      - ./logs:/app/logs
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
      - /dev/ttyUSB1:/dev/ttyUSB1
    environment:
      - PROMPTPLOT_CONFIG_PATH=/app/config/production.yaml
      - PROMPTPLOT_CACHE_DIR=/app/cache
      - PROMPTPLOT_LOG_LEVEL=INFO
      - PROMPTPLOT_ENABLE_MONITORING=true
    networks:
      - promptplot-network
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    container_name: promptplot-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    networks:
      - promptplot-network

  postgres:
    image: postgres:15-alpine
    container_name: promptplot-postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=promptplot
      - POSTGRES_USER=promptplot
      - POSTGRES_PASSWORD=secure_password
    networks:
      - promptplot-network

  nginx:
    image: nginx:alpine
    container_name: promptplot-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - promptplot
    networks:
      - promptplot-network

  prometheus:
    image: prom/prometheus:latest
    container_name: promptplot-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - promptplot-network

  grafana:
    image: grafana/grafana:latest
    container_name: promptplot-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin_password
    networks:
      - promptplot-network

volumes:
  redis-data:
  postgres-data:
  prometheus-data:
  grafana-data:

networks:
  promptplot-network:
    driver: bridge
```

### Kubernetes Deployment

#### Namespace
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: promptplot
```

#### ConfigMap
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: promptplot-config
  namespace: promptplot
data:
  config.yaml: |
    llm:
      default_provider: azure
      azure_endpoint: https://your-endpoint.openai.azure.com/
      max_retries: 3
    
    plotter:
      default_type: serial
      max_concurrent_jobs: 5
    
    workflow:
      enable_caching: true
      max_steps: 100
    
    performance:
      enable_monitoring: true
      cache_size_mb: 1024
```

#### Secret
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: promptplot-secrets
  namespace: promptplot
type: Opaque
data:
  azure-api-key: <base64-encoded-api-key>
  postgres-password: <base64-encoded-password>
```

#### Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: promptplot
  namespace: promptplot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: promptplot
  template:
    metadata:
      labels:
        app: promptplot
    spec:
      containers:
      - name: promptplot
        image: promptplot/promptplot:2.0.0
        ports:
        - containerPort: 8000
        env:
        - name: PROMPTPLOT_CONFIG_PATH
          value: /config/config.yaml
        - name: AZURE_OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: promptplot-secrets
              key: azure-api-key
        volumeMounts:
        - name: config
          mountPath: /config
        - name: cache
          mountPath: /app/cache
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: promptplot-config
      - name: cache
        persistentVolumeClaim:
          claimName: promptplot-cache-pvc
```

#### Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: promptplot-service
  namespace: promptplot
spec:
  selector:
    app: promptplot
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

#### Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: promptplot-ingress
  namespace: promptplot
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - promptplot.yourdomain.com
    secretName: promptplot-tls
  rules:
  - host: promptplot.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: promptplot-service
            port:
              number: 80
```

## Performance Optimization

### Application-Level Optimizations

#### Caching Strategy
```python
# config/production.yaml
cache:
  enabled: true
  type: hybrid  # memory + disk + redis
  memory_size_mb: 512
  disk_size_mb: 2048
  redis_url: redis://redis:6379/0
  ttl_seconds: 3600

performance:
  enable_profiling: true
  max_concurrent_workflows: 10
  gcode_batch_size: 100
  async_processing: true
```

#### Connection Pooling
```python
# Enhanced LLM provider with connection pooling
llm:
  azure:
    connection_pool_size: 20
    max_retries: 3
    timeout: 30
    rate_limit_rpm: 1000
  
  ollama:
    connection_pool_size: 10
    keep_alive: true
    timeout: 60
```

#### Memory Management
```python
# Memory optimization settings
memory:
  max_heap_size_mb: 4096
  gc_threshold: 0.8
  enable_memory_profiling: true
  command_history_limit: 1000
```

### Database Optimization

#### PostgreSQL Configuration
```sql
-- postgresql.conf optimizations
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

#### Redis Configuration
```conf
# redis.conf optimizations
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
tcp-keepalive 300
timeout 0
```

### System-Level Optimizations

#### Linux Kernel Parameters
```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_keepalive_time = 600
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

#### File System Optimization
```bash
# Mount options for cache directory
/dev/sdb1 /app/cache ext4 noatime,nodiratime,data=writeback 0 0

# Increase file descriptor limits
echo "promptplot soft nofile 65535" >> /etc/security/limits.conf
echo "promptplot hard nofile 65535" >> /etc/security/limits.conf
```

## Monitoring and Observability

### Metrics Collection

#### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'promptplot'
    static_configs:
      - targets: ['promptplot:8000']
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
```

#### Custom Metrics
```python
# Application metrics
from prometheus_client import Counter, Histogram, Gauge

# Workflow metrics
workflow_executions = Counter('promptplot_workflow_executions_total', 
                             'Total workflow executions', ['workflow_type', 'status'])
workflow_duration = Histogram('promptplot_workflow_duration_seconds',
                             'Workflow execution duration')
active_workflows = Gauge('promptplot_active_workflows',
                        'Number of active workflows')

# LLM metrics
llm_requests = Counter('promptplot_llm_requests_total',
                      'Total LLM requests', ['provider', 'model'])
llm_latency = Histogram('promptplot_llm_latency_seconds',
                       'LLM request latency')

# Plotter metrics
plotter_commands = Counter('promptplot_plotter_commands_total',
                          'Total plotter commands', ['plotter_id', 'command_type'])
plotter_errors = Counter('promptplot_plotter_errors_total',
                        'Plotter errors', ['plotter_id', 'error_type'])
```

### Logging Strategy

#### Structured Logging
```python
# logging configuration
logging:
  version: 1
  formatters:
    json:
      format: '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: json
      level: INFO
    file:
      class: logging.handlers.RotatingFileHandler
      filename: /app/logs/promptplot.log
      maxBytes: 100000000  # 100MB
      backupCount: 10
      formatter: json
      level: DEBUG
  loggers:
    promptplot:
      level: INFO
      handlers: [console, file]
      propagate: false
  root:
    level: WARNING
    handlers: [console]
```

#### Log Aggregation
```yaml
# Fluentd configuration for log aggregation
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /app/logs/*.log
      pos_file /var/log/fluentd-promptplot.log.pos
      tag promptplot.*
      format json
    </source>
    
    <match promptplot.**>
      @type elasticsearch
      host elasticsearch
      port 9200
      index_name promptplot
      type_name _doc
    </match>
```

### Health Checks

#### Application Health Endpoints
```python
# Health check endpoints
@app.route('/health')
def health_check():
    """Basic health check"""
    return {'status': 'healthy', 'timestamp': time.time()}

@app.route('/ready')
def readiness_check():
    """Readiness check with dependencies"""
    checks = {
        'database': check_database_connection(),
        'redis': check_redis_connection(),
        'llm_provider': check_llm_provider(),
        'plotter': check_plotter_connection()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return {'status': 'ready' if all_healthy else 'not_ready', 
            'checks': checks}, status_code

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()
```

## Security

### Authentication and Authorization

#### API Key Management
```python
# API key authentication
security:
  api_keys:
    enabled: true
    header_name: X-API-Key
    keys:
      - name: admin
        key: admin_api_key_here
        permissions: [read, write, admin]
      - name: readonly
        key: readonly_api_key_here
        permissions: [read]

  jwt:
    enabled: true
    secret_key: jwt_secret_key_here
    algorithm: HS256
    expiration_hours: 24
```

#### Network Security
```yaml
# Network policies
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: promptplot-network-policy
  namespace: promptplot
spec:
  podSelector:
    matchLabels:
      app: promptplot
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
```

### Data Protection

#### Encryption at Rest
```bash
# Encrypt sensitive configuration
kubectl create secret generic promptplot-secrets \
  --from-literal=azure-api-key="$(echo -n 'your-api-key' | base64)" \
  --from-literal=database-password="$(echo -n 'your-password' | base64)"
```

#### Encryption in Transit
```yaml
# TLS configuration
tls:
  enabled: true
  cert_file: /etc/ssl/certs/promptplot.crt
  key_file: /etc/ssl/private/promptplot.key
  min_version: "1.2"
  cipher_suites:
    - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
```

## Backup and Recovery

### Backup Strategy

#### Configuration Backup
```bash
#!/bin/bash
# backup-config.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/promptplot"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup configuration
kubectl get configmap promptplot-config -o yaml > "$BACKUP_DIR/config_$DATE.yaml"
kubectl get secret promptplot-secrets -o yaml > "$BACKUP_DIR/secrets_$DATE.yaml"

# Backup database
pg_dump -h postgres -U promptplot promptplot > "$BACKUP_DIR/database_$DATE.sql"

# Backup cache (optional)
tar -czf "$BACKUP_DIR/cache_$DATE.tar.gz" /app/cache/

echo "Backup completed: $BACKUP_DIR"
```

#### Automated Backup
```yaml
# CronJob for automated backups
apiVersion: batch/v1
kind: CronJob
metadata:
  name: promptplot-backup
  namespace: promptplot
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h postgres -U promptplot promptplot > /backup/database_$(date +%Y%m%d_%H%M%S).sql
              find /backup -name "database_*.sql" -mtime +7 -delete
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

### Disaster Recovery

#### Recovery Procedures
```bash
#!/bin/bash
# restore-from-backup.sh
BACKUP_DATE=$1

if [ -z "$BACKUP_DATE" ]; then
    echo "Usage: $0 <backup_date>"
    exit 1
fi

BACKUP_DIR="/backups/promptplot"

# Restore configuration
kubectl apply -f "$BACKUP_DIR/config_$BACKUP_DATE.yaml"
kubectl apply -f "$BACKUP_DIR/secrets_$BACKUP_DATE.yaml"

# Restore database
psql -h postgres -U promptplot promptplot < "$BACKUP_DIR/database_$BACKUP_DATE.sql"

# Restore cache
tar -xzf "$BACKUP_DIR/cache_$BACKUP_DATE.tar.gz" -C /

echo "Restore completed from backup: $BACKUP_DATE"
```

## Scaling Strategies

### Horizontal Scaling

#### Auto-scaling Configuration
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: promptplot-hpa
  namespace: promptplot
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: promptplot
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### Vertical Scaling

#### Resource Optimization
```yaml
# Vertical Pod Autoscaler
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: promptplot-vpa
  namespace: promptplot
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: promptplot
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: promptplot
      maxAllowed:
        cpu: 2
        memory: 4Gi
      minAllowed:
        cpu: 100m
        memory: 128Mi
```

## Maintenance

### Update Procedures

#### Rolling Updates
```bash
#!/bin/bash
# rolling-update.sh
NEW_VERSION=$1

if [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <new_version>"
    exit 1
fi

# Update deployment image
kubectl set image deployment/promptplot promptplot=promptplot/promptplot:$NEW_VERSION -n promptplot

# Wait for rollout to complete
kubectl rollout status deployment/promptplot -n promptplot

# Verify deployment
kubectl get pods -n promptplot
```

#### Rollback Procedures
```bash
#!/bin/bash
# rollback.sh

# Check rollout history
kubectl rollout history deployment/promptplot -n promptplot

# Rollback to previous version
kubectl rollout undo deployment/promptplot -n promptplot

# Wait for rollback to complete
kubectl rollout status deployment/promptplot -n promptplot
```

### Maintenance Windows

#### Scheduled Maintenance
```yaml
# Maintenance mode configuration
maintenance:
  enabled: false
  message: "System is under maintenance. Please try again later."
  allowed_ips:
    - 192.168.1.0/24  # Admin network
  start_time: "2024-01-15T02:00:00Z"
  end_time: "2024-01-15T04:00:00Z"
```

This deployment guide provides comprehensive coverage of production deployment strategies, performance optimization, monitoring, security, and maintenance procedures for PromptPlot v2.0.