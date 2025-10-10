# Architecture Documentation

This directory contains comprehensive documentation about the OmniScrape system architecture, design decisions, and technical implementation details.

## 🏗️ System Architecture Overview

OmniScrape is built as a modern, scalable web scraping service with a multi-layered extraction strategy and comprehensive API interface.

## 📐 High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client/UI     │    │   FastAPI       │    │   Extraction    │
│                 │    │   Server        │    │   Pipeline      │
│ • Web Interface │◄──►│                 │◄──►│                 │
│ • API Clients   │    │ • REST Endpoints│    │ • Multi-method  │
│ • Labs Page     │    │ • Request Val.  │    │ • Fallback      │
└─────────────────┘    │ • Error Handling│    │ • Token Tracking│
                        └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                        ┌─────────────────┐    ┌─────────────────┐
                        │   Browser       │    │   LLM Services  │
                        │   Engine        │    │                 │
                        │                 │    │ • OpenAI API    │
                        │ • Playwright    │    │ • ScrapeGraphAI │
                        │ • Anti-bot      │    │ • Token Usage   │
                        │ • Proxy Support │    │ • Monkey Patch  │
                        └─────────────────┘    └─────────────────┘
```

## 🔄 Data Flow Architecture

### Request Processing Pipeline

```
1. Client Request
   ↓
2. FastAPI Router
   ↓
3. Request Validation (Pydantic)
   ↓
4. Pipeline Orchestration
   ↓
5. Browser Fetching (Playwright)
   ↓
6. Extraction Methods (Cascading)
   ├── Structured Data (JSON-LD, Microdata, OpenGraph)
   ├── Readability (Clean text extraction)
   └── LLM Fallback (ScrapeGraphAI)
   ↓
7. Result Normalization
   ↓
8. Response Formatting
   ↓
9. Client Response
```

### Extraction Strategy

```
URL Input
    ↓
HTML Fetching (Playwright + Anti-bot)
    ↓
┌─────────────────────────────────────────┐
│           Extraction Methods            │
├─────────────────┬───────────────────────┤
│ Structured Data  │ Readability          │
│ • JSON-LD       │ • Content cleaning   │
│ • Microdata     │ • Title extraction   │
│ • OpenGraph     │ • Image detection    │
└─────────────────┴───────────────────────┘
    ↓ (if insufficient content)
LLM Extraction (ScrapeGraphAI)
    ↓
Result Aggregation & Normalization
    ↓
JSON Response with Metadata
```

## 🧩 Component Architecture

### Core Components

#### 1. API Layer (`src/api/`)
- **FastAPI Application**: Main web server
- **Request Handling**: Input validation and routing
- **Response Formatting**: JSON responses with metadata
- **Error Handling**: Comprehensive error management
- **UI Integration**: Web interface and Labs page

#### 2. Core Engine (`src/core/`)
- **Pipeline Orchestration**: Extraction workflow management
- **Browser Engine**: Playwright integration with anti-bot features
- **LLM Wrapper**: Token usage tracking and API management
- **Data Models**: Pydantic schemas for validation

#### 3. Extractors (`src/extractors/`)
- **Structured Data**: JSON-LD, Microdata, OpenGraph parsing
- **Readability**: Clean text extraction using readability-lxml
- **Pattern Matching**: Regex-based data extraction
- **LLM Integration**: ScrapeGraphAI with monkey patching

#### 4. Labs (`src/labs/`)
- **Graph Implementations**: All ScrapeGraphAI graph types
- **Interactive Testing**: Real-time graph execution
- **Configuration Management**: Graph-specific settings
- **Async Processing**: Non-blocking graph execution

## 🔧 Technical Implementation

### Technology Stack

#### Backend Framework
- **FastAPI**: Modern, fast web framework
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for production

#### Web Scraping
- **Playwright**: Headless browser automation
- **BeautifulSoup4**: HTML parsing
- **Readability-lxml**: Content extraction
- **Extruct**: Structured data parsing

#### LLM Integration
- **ScrapeGraphAI**: LLM-powered extraction graphs
- **LangChain**: LLM framework integration
- **OpenAI API**: Primary LLM provider
- **Monkey Patching**: Token usage interception

#### Data Processing
- **Tenacity**: Retry mechanisms
- **Concurrent.futures**: Thread pool execution
- **Asyncio**: Async/await support

### Anti-Bot Measures

#### Browser Stealth
```python
# User agent rotation
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
    # ... more agents
]

# Stealth JavaScript injection
stealth_script = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = {runtime: {}};
// ... more stealth measures
"""
```

#### Human Behavior Simulation
- **Mouse Movements**: Random cursor movements
- **Scrolling**: Gradual page scrolling
- **Typing**: Human-like typing patterns
- **Timing**: Random delays between actions

#### Resource Blocking
- **Images**: Block unnecessary images
- **Analytics**: Block tracking scripts
- **Ads**: Block advertisement content
- **Fonts**: Block custom fonts

### Token Usage Tracking

#### Monkey Patching Strategy
```python
# Intercept LangChain calls
original_generate = langchain_openai.chat_models.ChatOpenAI._generate

def patched_generate(self, messages, stop=None, run_manager=None, **kwargs):
    # Filter unsupported parameters
    filtered_kwargs = {k: v for k, v in kwargs.items() 
                      if k not in ['provider', 'model_tokens']}
    
    # Call original method
    result = original_generate(self, messages, stop=stop, 
                              run_manager=run_manager, **filtered_kwargs)
    
    # Extract token usage
    if hasattr(result, 'llm_output') and result.llm_output:
        usage_data = result.llm_output.get('token_usage')
        if usage_data:
            _tracker.set_usage(usage_data)
    
    return result

# Apply patch
langchain_openai.chat_models.ChatOpenAI._generate = patched_generate
```

## 🚀 Performance Architecture

### Caching Strategy
- **HTML Caching**: Temporary storage of fetched content
- **Result Caching**: Cache extraction results by URL hash
- **LLM Response Caching**: Cache LLM responses for similar content

### Concurrency Model
- **Async Processing**: Non-blocking request handling
- **Thread Pool**: LLM calls in separate threads
- **Connection Pooling**: Reuse HTTP connections
- **Parallel Extraction**: Multiple method execution

### Resource Management
- **Memory Optimization**: Efficient HTML parsing
- **CPU Optimization**: Optimized regex patterns
- **Network Optimization**: Connection pooling and retries
- **Browser Pool**: Reuse browser instances

## 🔒 Security Architecture

### Input Validation
- **URL Validation**: Verify URL format and accessibility
- **Content Sanitization**: Remove malicious content
- **Prompt Filtering**: Validate LLM prompts
- **Size Limits**: Limit request and response sizes

### API Security
- **Rate Limiting**: Prevent abuse and overuse
- **Authentication**: API key validation
- **CORS**: Cross-origin resource sharing
- **HTTPS**: Encrypted communication

### Data Protection
- **Sensitive Data**: Remove PII from responses
- **Content Filtering**: Block inappropriate content
- **Audit Logging**: Track API usage
- **Error Sanitization**: Remove sensitive error details

## 📊 Monitoring Architecture

### Metrics Collection
- **Performance Metrics**: Response times, throughput
- **Usage Metrics**: API calls, graph usage
- **Error Metrics**: Failure rates, error types
- **Resource Metrics**: CPU, memory, network usage

### Logging Strategy
- **Structured Logging**: JSON-formatted logs
- **Log Levels**: Debug, Info, Warning, Error
- **Context Preservation**: Request IDs, user agents
- **Log Aggregation**: Centralized log collection

### Health & Status Monitoring
- **Status UI**: `/status` (includes OpenAI RSS incidents)
- **Health JSON**: `/health.json` (local checks and system metrics)
- **Dependency Checks**: External service status
- **Performance Monitoring**: Response time tracking
- **Alert System**: Automated error notifications

## 🔄 Deployment Architecture

### Development Environment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Development   │    │   Testing       │    │   Staging       │
│   Server        │    │   Environment   │    │   Environment   │
│                 │    │                 │    │                 │
│ • Hot Reload    │    │ • Unit Tests    │    │ • Integration   │
│ • Debug Mode    │    │ • Mock APIs     │    │ • Performance   │
│ • Local APIs    │    │ • Test Data     │    │ • Production    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Production Environment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Application    │    │   Database      │
│                 │    │   Servers        │    │                 │
│ • SSL/TLS       │    │ • FastAPI       │    │ • Redis Cache   │
│ • Rate Limiting │    │ • Uvicorn       │    │ • Log Storage   │
│ • Health Checks │    │ • Process Mgmt  │    │ • Metrics DB    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🧪 Testing Architecture

### Test Strategy
- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **End-to-End Tests**: Full workflow testing
- **Performance Tests**: Load and stress testing

### Test Environment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Test Data     │    │   Mock Services │    │   Test Runner   │
│                 │    │                 │    │                 │
│ • Sample URLs   │    │ • Mock APIs     │    │ • Pytest        │
│ • Test Content  │    │ • Fake LLM      │    │ • Coverage      │
│ • Edge Cases    │    │ • Test Browser  │    │ • CI/CD         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Configuration Architecture

### Environment Configuration
```bash
# Core Settings
SCRAPEGRAPH_MODEL=gpt-4o-mini
MAX_RENDER_MS=15000
HEADLESS=true

# API Keys
OPENAI_API_KEY=your_key
BING_SEARCH_API_KEY=your_key

# Proxy Settings
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=https://proxy:8080

# Performance
MAX_CONCURRENT_REQUESTS=10
CACHE_TTL=3600
```

### Configuration Management
- **Environment Variables**: Primary configuration method
- **Configuration Files**: Optional config file support
- **Runtime Configuration**: Dynamic configuration updates
- **Validation**: Configuration validation and defaults

## 📈 Scalability Architecture

### Horizontal Scaling
- **Load Balancing**: Distribute requests across instances
- **Stateless Design**: No server-side session storage
- **Container Orchestration**: Docker and Kubernetes support
- **Auto-scaling**: Dynamic instance management

### Vertical Scaling
- **Resource Optimization**: Efficient memory and CPU usage
- **Connection Pooling**: Reuse database connections
- **Caching**: Reduce external API calls
- **Async Processing**: Non-blocking operations

## 🔄 Maintenance Architecture

### Update Strategy
- **Zero-downtime Deployments**: Rolling updates
- **Feature Flags**: Gradual feature rollouts
- **Backward Compatibility**: API versioning
- **Rollback Capability**: Quick reversion

### Monitoring and Alerting
- **Health Monitoring**: Continuous system health checks
- **Performance Monitoring**: Real-time performance metrics
- **Error Tracking**: Comprehensive error logging
- **Alert System**: Automated notifications

This architecture provides a robust, scalable, and maintainable foundation for the OmniScrape web scraping service.
