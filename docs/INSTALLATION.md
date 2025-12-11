# PromptPlot v2.0 Installation Guide

This guide provides comprehensive installation instructions for PromptPlot v2.0, including system requirements, installation methods, and deployment options.

## System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)

### Recommended Requirements
- **Python**: 3.10 or higher
- **RAM**: 16GB for large drawing operations
- **Storage**: 10GB free space (for caching and examples)
- **GPU**: Optional, for computer vision acceleration

### Hardware Requirements
- **Serial Port**: USB or native serial port for plotter connection
- **Plotter**: Compatible pen plotter (AxiDraw, custom GRBL-based, etc.)
- **Camera**: Optional, for computer vision features

## Installation Methods

### Method 1: pip Installation (Recommended)

#### Basic Installation
```bash
pip install promptplot
```

#### Installation with All Features
```bash
pip install promptplot[all]
```

#### Installation with Specific Features
```bash
# Azure OpenAI support
pip install promptplot[azure]

# Local Ollama support
pip install promptplot[ollama]

# Computer vision features
pip install promptplot[vision]

# Performance optimizations
pip install promptplot[performance]

# Development tools
pip install promptplot[dev]
```

### Method 2: Development Installation

#### Clone Repository
```bash
git clone https://github.com/promptplot/promptplot.git
cd promptplot
```

#### Create Virtual Environment
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

#### Install in Development Mode
```bash
pip install -e .[dev,all]
```

### Method 3: Docker Installation

#### Pull Docker Image
```bash
docker pull promptplot/promptplot:latest
```

#### Run with Docker
```bash
docker run -it --device=/dev/ttyUSB0 promptplot/promptplot:latest
```

#### Docker Compose
```yaml
version: '3.8'
services:
  promptplot:
    image: promptplot/promptplot:latest
    volumes:
      - ./config:/app/config
      - ./results:/app/results
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    environment:
      - PROMPTPLOT_CONFIG_PATH=/app/config
```

## Platform-Specific Installation

### Windows

#### Prerequisites
```powershell
# Install Python from python.org or Microsoft Store
# Install Git for Windows
# Install Visual Studio Build Tools (for C extensions)
```

#### Installation
```powershell
pip install promptplot[all]

# For serial port access
pip install pywin32
```

#### Common Issues
- **Serial Port Access**: Run as Administrator or adjust COM port permissions
- **Build Tools**: Install Visual Studio Build Tools for C++ if compilation fails

### macOS

#### Prerequisites
```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.10

# Install development tools
xcode-select --install
```

#### Installation
```bash
pip3 install promptplot[all]
```

#### Common Issues
- **Permission Denied**: Use `sudo` or adjust permissions for serial ports
- **Xcode Tools**: Install Xcode command line tools for compilation

### Linux (Ubuntu/Debian)

#### Prerequisites
```bash
# Update package list
sudo apt update

# Install Python and development tools
sudo apt install python3 python3-pip python3-venv
sudo apt install build-essential python3-dev
sudo apt install libusb-1.0-0-dev libudev-dev

# For serial port access
sudo usermod -a -G dialout $USER
```

#### Installation
```bash
pip3 install promptplot[all]
```

#### Common Issues
- **Serial Port Permissions**: Add user to `dialout` group and logout/login
- **USB Device Access**: Install `udev` rules for plotter devices

### Raspberry Pi

#### Prerequisites
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3-pip python3-venv
sudo apt install python3-numpy python3-matplotlib
sudo apt install libatlas-base-dev libopenblas-dev
```

#### Installation
```bash
# Use system packages for heavy dependencies
pip3 install promptplot --no-deps
pip3 install -r requirements-rpi.txt
```

## Configuration

### Initial Setup
```bash
# Create configuration directory
promptplot config init

# Show current configuration
promptplot config show

# Set LLM provider
promptplot config set llm.default_provider ollama
```

### Environment Variables
```bash
# Configuration file path
export PROMPTPLOT_CONFIG_PATH=/path/to/config

# Cache directory
export PROMPTPLOT_CACHE_DIR=/path/to/cache

# Log level
export PROMPTPLOT_LOG_LEVEL=INFO

# Enable performance optimizations
export PROMPTPLOT_ENABLE_CACHE=1
export PROMPTPLOT_BUILD_EXTENSIONS=1
```

### Configuration File
Create `~/.promptplot/config.yaml`:
```yaml
llm:
  default_provider: ollama
  ollama_model: llama3.2:3b

plotter:
  default_type: simulated
  serial_port: /dev/ttyUSB0

workflow:
  max_retries: 3
  enable_caching: true
```

## Verification

### Test Installation
```bash
# Check version
promptplot --version

# Test configuration
promptplot config show

# Test plotter connection (simulated)
promptplot plotter test --simulate

# Run simple workflow
promptplot workflow simple "Draw a test line" --simulate
```

### Run Examples
```bash
# Clone examples (if not installed via pip)
git clone https://github.com/promptplot/promptplot-examples.git

# Run basic example
cd promptplot-examples
python basic/simple_drawing.py
```

## Performance Optimization

### Enable Caching
```bash
# Enable G-code caching
promptplot config set workflow.enable_caching true

# Set cache directory
promptplot config set cache.directory /path/to/fast/storage
```

### Compile Extensions
```bash
# Install with C extensions for better performance
PROMPTPLOT_BUILD_EXTENSIONS=1 pip install promptplot[performance]
```

### Memory Optimization
```bash
# Limit memory usage
promptplot config set performance.max_memory_mb 4096

# Enable memory monitoring
promptplot config set performance.enable_monitoring true
```

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Check Python version
python --version

# Check installed packages
pip list | grep promptplot

# Reinstall with dependencies
pip uninstall promptplot
pip install promptplot[all]
```

#### Serial Port Issues
```bash
# List available ports
promptplot plotter list-ports

# Test port access
promptplot plotter test --port /dev/ttyUSB0

# Check permissions (Linux/macOS)
ls -l /dev/ttyUSB0
sudo chmod 666 /dev/ttyUSB0
```

#### LLM Connection Issues
```bash
# Test Ollama connection
curl http://localhost:11434/api/tags

# Test Azure OpenAI (with API key)
promptplot config set llm.azure_api_key YOUR_KEY
promptplot workflow simple "test" --simulate
```

### Performance Issues

#### Slow G-code Generation
- Enable caching: `promptplot config set workflow.enable_caching true`
- Use faster LLM model: `promptplot config set llm.ollama_model llama3.2:1b`
- Increase timeout: `promptplot config set llm.timeout 60`

#### High Memory Usage
- Limit cache size: `promptplot config set cache.max_size_mb 1024`
- Use streaming workflows for large drawings
- Enable memory monitoring: `promptplot config set performance.enable_monitoring true`

### Getting Help

#### Documentation
- Online Documentation: https://promptplot.readthedocs.io/
- API Reference: https://promptplot.readthedocs.io/en/latest/api/
- Examples: https://github.com/promptplot/promptplot-examples

#### Community Support
- GitHub Issues: https://github.com/promptplot/promptplot/issues
- Discussions: https://github.com/promptplot/promptplot/discussions
- Discord: https://discord.gg/promptplot

#### Professional Support
- Email: support@promptplot.dev
- Commercial Support: https://promptplot.dev/support

## Deployment Options

### Production Deployment

#### Systemd Service (Linux)
```ini
[Unit]
Description=PromptPlot Service
After=network.target

[Service]
Type=simple
User=promptplot
WorkingDirectory=/opt/promptplot
ExecStart=/opt/promptplot/venv/bin/python -m promptplot.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Docker Production
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["python", "-m", "promptplot.server"]
```

#### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: promptplot
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
        image: promptplot/promptplot:latest
        ports:
        - containerPort: 8000
        env:
        - name: PROMPTPLOT_CONFIG_PATH
          value: /config/promptplot.yaml
        volumeMounts:
        - name: config
          mountPath: /config
      volumes:
      - name: config
        configMap:
          name: promptplot-config
```

### Cloud Deployment

#### AWS EC2
```bash
# Launch EC2 instance with Ubuntu
# Install Docker
sudo apt update
sudo apt install docker.io
sudo systemctl start docker

# Deploy PromptPlot
docker run -d --name promptplot \
  -p 8000:8000 \
  -v /opt/promptplot/config:/app/config \
  promptplot/promptplot:latest
```

#### Google Cloud Run
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: promptplot
spec:
  template:
    spec:
      containers:
      - image: gcr.io/PROJECT_ID/promptplot
        ports:
        - containerPort: 8000
        env:
        - name: PROMPTPLOT_CONFIG_PATH
          value: /config/promptplot.yaml
```

#### Azure Container Instances
```bash
az container create \
  --resource-group promptplot-rg \
  --name promptplot \
  --image promptplot/promptplot:latest \
  --ports 8000 \
  --environment-variables PROMPTPLOT_CONFIG_PATH=/config/promptplot.yaml
```

## Security Considerations

### API Keys
- Store API keys in environment variables or secure key management
- Use Azure Key Vault, AWS Secrets Manager, or similar services
- Never commit API keys to version control

### Network Security
- Use HTTPS for all external communications
- Implement proper firewall rules
- Use VPN for remote plotter access

### File Permissions
- Run with minimal required permissions
- Use dedicated user account for production
- Secure configuration and cache directories

## Monitoring and Logging

### Enable Logging
```bash
# Set log level
promptplot config set log_level DEBUG

# Set log file
promptplot config set log_file /var/log/promptplot.log

# Enable performance monitoring
promptplot config set performance.enable_monitoring true
```

### Monitoring Tools
- Prometheus metrics endpoint
- Grafana dashboards
- Health check endpoints
- Performance profiling

## Updates and Maintenance

### Update PromptPlot
```bash
# Update to latest version
pip install --upgrade promptplot

# Update with all features
pip install --upgrade promptplot[all]

# Check for updates
promptplot --version
```

### Backup Configuration
```bash
# Backup configuration
cp ~/.promptplot/config.yaml ~/.promptplot/config.yaml.backup

# Backup cache (optional)
tar -czf promptplot-cache-backup.tar.gz ~/.promptplot/cache/
```

### Migration Guide
See [MIGRATION.md](MIGRATION.md) for version-specific migration instructions.