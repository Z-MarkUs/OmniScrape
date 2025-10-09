# Configuration

This directory contains configuration files and templates for the OmniScrape service.

## 📁 Configuration Files

### Environment Configuration
- **.env.example** - Environment variables template
- **.env.local** - Local development configuration
- **.env.production** - Production configuration template

### Application Configuration
- **config.yaml** - Application settings
- **logging.yaml** - Logging configuration
- **proxy.yaml** - Proxy settings

## 🔧 Environment Variables

### Required Variables
```bash
# OpenAI API Key (required for LLM features)
OPENAI_API_KEY=your_openai_api_key_here
```

### Optional Variables
```bash
# LLM Model Configuration
SCRAPEGRAPH_MODEL=gpt-4o-mini

# Browser Configuration
MAX_RENDER_MS=15000
HEADLESS=true

# Proxy Configuration
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=https://proxy:8080

# Bing Search API (for SearchGraph)
BING_SEARCH_API_KEY=your_bing_api_key_here

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json

# Performance Configuration
MAX_CONCURRENT_REQUESTS=10
CACHE_TTL=3600
```

## 🚀 Quick Setup

### 1. Copy Environment Template
```bash
cp .env.example .env
```

### 2. Edit Configuration
```bash
# Edit .env file with your settings
nano .env
```

### 3. Validate Configuration
```bash
# Check if all required variables are set
python -c "from dotenv import load_dotenv; load_dotenv(); print('Configuration loaded successfully')"
```

## 🔒 Security Configuration

### API Key Management
```bash
# Use environment variables (recommended)
export OPENAI_API_KEY="your_key_here"

# Or use .env file (for development only)
echo "OPENAI_API_KEY=your_key_here" >> .env
```

### Proxy Configuration
```bash
# HTTP Proxy
export HTTP_PROXY="http://username:password@proxy.example.com:8080"

# HTTPS Proxy
export HTTPS_PROXY="https://username:password@proxy.example.com:8080"

# No Proxy (exclude certain domains)
export NO_PROXY="localhost,127.0.0.1,.local"
```

## 🧪 Development Configuration

### Local Development
```bash
# .env.local
OPENAI_API_KEY=your_dev_key
SCRAPEGRAPH_MODEL=gpt-4o-mini
MAX_RENDER_MS=30000
HEADLESS=false
LOG_LEVEL=DEBUG
```

### Testing Configuration
```bash
# .env.test
OPENAI_API_KEY=test_key
SCRAPEGRAPH_MODEL=gpt-4o-mini
MAX_RENDER_MS=5000
HEADLESS=true
LOG_LEVEL=WARNING
```

## 🚀 Production Configuration

### Production Environment
```bash
# .env.production
OPENAI_API_KEY=your_production_key
SCRAPEGRAPH_MODEL=gpt-4o-mini
MAX_RENDER_MS=15000
HEADLESS=true
LOG_LEVEL=INFO
LOG_FORMAT=json
MAX_CONCURRENT_REQUESTS=20
CACHE_TTL=7200
```

### Docker Configuration
```bash
# docker-compose.yml
version: '3.8'
services:
  omniscrape:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SCRAPEGRAPH_MODEL=gpt-4o-mini
      - MAX_RENDER_MS=15000
    volumes:
      - ./config:/app/config
```

## 📊 Monitoring Configuration

### Logging Configuration
```yaml
# logging.yaml
version: 1
formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  json:
    format: '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'

handlers:
  console:
    class: logging.StreamHandler
    formatter: default
    level: INFO
  file:
    class: logging.FileHandler
    filename: logs/omniscrape.log
    formatter: json
    level: DEBUG

loggers:
  omniscrape:
    level: DEBUG
    handlers: [console, file]
    propagate: false
```

### Metrics Configuration
```yaml
# metrics.yaml
metrics:
  enabled: true
  port: 9090
  path: /metrics
  
prometheus:
  enabled: true
  namespace: omniscrape
  
health_check:
  enabled: true
  interval: 30
  timeout: 5
```

## 🔧 Advanced Configuration

### Custom Browser Settings
```yaml
# browser.yaml
browser:
  headless: true
  viewport:
    width: 1920
    height: 1080
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  stealth:
    enabled: true
    remove_webdriver: true
    mock_plugins: true
    mock_languages: true
  resources:
    block_images: false
    block_css: false
    block_js: false
    block_analytics: true
```

### Proxy Rotation Configuration
```yaml
# proxy.yaml
proxy:
  enabled: true
  rotation: per_request
  urls:
    - "http://proxy1:8080"
    - "http://proxy2:8080"
    - "http://proxy3:8080"
  authentication:
    username: "proxy_user"
    password: "proxy_pass"
  timeout: 30
  retries: 3
```

### LLM Configuration
```yaml
# llm.yaml
llm:
  provider: openai
  model: gpt-4o-mini
  max_tokens: 128000
  temperature: 0.1
  timeout: 60
  retries: 3
  rate_limit:
    requests_per_minute: 60
    tokens_per_minute: 150000
```

## 🛠️ Configuration Validation

### Python Validation Script
```python
# validate_config.py
import os
from dotenv import load_dotenv

def validate_config():
    """Validate configuration settings"""
    load_dotenv()
    
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Missing required variables: {missing_vars}")
        return False
    
    # Validate optional variables
    max_render_ms = os.getenv("MAX_RENDER_MS", "15000")
    try:
        int(max_render_ms)
    except ValueError:
        print("MAX_RENDER_MS must be a number")
        return False
    
    print("Configuration validation passed!")
    return True

if __name__ == "__main__":
    validate_config()
```

### Configuration Test
```bash
# Test configuration
python validate_config.py

# Expected output:
# Configuration validation passed!
```

## 🔄 Configuration Management

### Environment-Specific Configs
```bash
# Development
cp .env.example .env.dev
# Edit .env.dev with development settings

# Staging
cp .env.example .env.staging
# Edit .env.staging with staging settings

# Production
cp .env.example .env.prod
# Edit .env.prod with production settings
```

### Configuration Loading
```python
# config_loader.py
import os
from dotenv import load_dotenv

def load_config(env="development"):
    """Load configuration based on environment"""
    env_file = f".env.{env}"
    
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()  # Load default .env
    
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini"),
        "max_render_ms": int(os.getenv("MAX_RENDER_MS", "15000")),
        "headless": os.getenv("HEADLESS", "true").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO")
    }

# Usage
config = load_config("production")
```

## 📚 Additional Resources

- **Environment Variables**: [../docs/api/README.md](../docs/api/README.md)
- **Deployment Guide**: [../docs/architecture/README.md](../docs/architecture/README.md)
- **Main README**: [../README.md](../README.md)
