from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Literal
import orjson
import asyncio
from src.core.pipeline import extract

class ExtractRequest(BaseModel):
    url: HttpUrl
    kind: Literal["article", "product"]
    llmMode: Literal["none", "llm", "auto"] = "auto"

app = FastAPI(
    title="OmniScrape API",
    description="""
    ## 🚀 OmniScrape - Advanced Web Scraping Service
    
    A sophisticated, multi-layered web scraping service that can extract articles and products from any website using a cascading fallback strategy.
    
    ### ✨ Features
    - **Multi-layered Extraction**: Structured data → Readability → LLM fallback
    - **Article Extraction**: Title, author, content, images, publication date
    - **Product Extraction**: Name, price, currency, description, images, SKU
    - **Browser Rendering**: Playwright for JavaScript-heavy sites
    - **Interactive Labs**: Test ScrapeGraphAI capabilities with real-time results
    - **Token Usage Tracking**: Real-time LLM token consumption monitoring
    
    ### 🔧 Extraction Methods
    1. **Structured Data** - JSON-LD, Microdata, OpenGraph
    2. **Readability** - Clean text extraction using readability-lxml
    3. **LLM Fallback** - ScrapeGraphAI for complex cases
    
    ### 🧪 Labs Features
    - **SmartScraperGraph** - Single page extraction with custom prompts
    - **SearchGraph** - Multi-page search-based extraction
    - **SpeechGraph** - Audio generation from web content
    - **ScriptCreatorGraph** - Python script generation
    - **SmartScraperMultiGraph** - Multi-page extraction
    - **ScriptCreatorMultiGraph** - Multi-page script generation
    
    ### 📚 Documentation
    - **[API Documentation](../docs/api/)** - Complete API reference
    - **[Extractors Guide](../docs/extractors/)** - Extraction methods
    - **[Labs Documentation](../docs/labs/)** - Interactive testing
    - **[Architecture Overview](../docs/architecture/)** - System design
    
    ### 🔑 Authentication
    All LLM-powered features require an OpenAI API key:
    ```bash
    export OPENAI_API_KEY="your_openai_api_key"
    ```
    
    Optional: Bing Search API key for SearchGraph:
    ```bash
    export BING_SEARCH_API_KEY="your_bing_api_key"
    ```
    """,
    version="0.1.0",
    contact={
        "name": "OmniScrape API",
        "url": "https://github.com/Z-MarkUs/OmniScrape",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://your-domain.com",
            "description": "Production server"
        }
    ],
    tags_metadata=[
        {
            "name": "extraction",
            "description": "Main extraction endpoints for articles and products",
        },
        {
            "name": "labs",
            "description": "Interactive ScrapeGraphAI testing endpoints",
        },
        {
            "name": "health",
            "description": "Health check and monitoring endpoints",
        },
    ]
)

@app.get("/", response_class=HTMLResponse)
def root():
    return (
        """
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
          <title>OmniScrape API</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 32px; color: #222; }
            h1 { margin-bottom: 8px; }
            .tag { display: inline-block; background: #eef2ff; color: #3730a3; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
            .links a { display: inline-block; margin-right: 12px; color: #2563eb; text-decoration: none; }
            .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin-top: 20px; }
            label { display:block; margin: 8px 0 4px; font-weight: 600; }
            input, select { box-sizing: border-box; width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 8px; }
            button { margin-top: 12px; background: #111827; color: white; border: none; padding: 10px 14px; border-radius: 8px; cursor: pointer; }
            pre { background: #0b1020; color: #e5e7eb; padding: 12px; border-radius: 8px; overflow:auto; }
          </style>
        </head>
        <body>
          <h1>OmniScrape API</h1>
          <div class=\"tag\">v0.1.0</div>
          <p>Extract articles and products using structured data, readability, and LLM fallbacks.</p>
          <div class=\"links\">
            <a href=\"/docs\">Swagger Docs</a>
            <a href=\"/redoc\">ReDoc</a>
            <a href=\"/health\">Health</a>
            <a href=\"/labs\">Labs</a>
          </div>

          <div class=\"card\">
            <h2>Quick Test</h2>
            <form id=\"form\">
              <label for=\"url\">URL</label>
              <input id=\"url\" name=\"url\" type=\"url\" placeholder=\"https://example.com\" required />
              <label for=\"kind\">Kind</label>
              <select id=\"kind\" name=\"kind\">
                <option value=\"article\">article</option>
                <option value=\"product\">product</option>
              </select>
              
              <div style=\"margin: 20px 0;\">
                <h4 style=\"margin: 0 0 15px 0; color: #333; font-size: 16px;\">Extraction Method</h4>
                
                <div style=\"display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;\">
                  <label style=\"display: block; cursor: pointer; padding: 16px; background: white; border: 2px solid #e9ecef; border-radius: 8px; text-align: center; transition: all 0.2s;\">
                    <input type=\"radio\" name=\"llmMode\" value=\"none\" style=\"margin-bottom: 8px;\" />
                    <div style=\"font-size: 18px; margin-bottom: 8px; color: #4CAF50;\">SD</div>
                    <div style=\"font-weight: 600; color: #495057; margin-bottom: 4px;\">Structured Data</div>
                    <div style=\"font-size: 12px; color: #6c757d; line-height: 1.3;\">JSON-LD + Readability<br/>No LLM costs</div>
                  </label>
                  
                  <label style=\"display: block; cursor: pointer; padding: 16px; background: white; border: 2px solid #e9ecef; border-radius: 8px; text-align: center; transition: all 0.2s;\">
                    <input type=\"radio\" name=\"llmMode\" value=\"llm\" style=\"margin-bottom: 8px;\" />
                    <div style=\"font-size: 18px; margin-bottom: 8px; color: #F44336;\">LLM</div>
                    <div style=\"font-weight: 600; color: #495057; margin-bottom: 4px;\">LLM Direct</div>
                    <div style=\"font-size: 12px; color: #6c757d; line-height: 1.3;\">Direct AI processing<br/>Token consumption</div>
                  </label>
                  
                  <label style=\"display: block; cursor: pointer; padding: 16px; background: white; border: 2px solid #e9ecef; border-radius: 8px; text-align: center; transition: all 0.2s;\">
                    <input type=\"radio\" name=\"llmMode\" value=\"auto\" checked style=\"margin-bottom: 8px;\" />
                    <div style=\"font-size: 18px; margin-bottom: 8px; color: #FFC107;\">AUTO</div>
                    <div style=\"font-weight: 600; color: #495057; margin-bottom: 4px;\">Smart Fallback</div>
                    <div style=\"font-size: 12px; color: #6c757d; line-height: 1.3;\">SD first, LLM fallback<br/>Optimal performance</div>
                  </label>
                </div>
                
                <style>
                  label:hover { border-color: #007bff !important; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,123,255,0.15); }
                  label.selected { 
                    border-color: #007bff !important; 
                    background-color: #f8f9fa !important; 
                    box-shadow: 0 4px 12px rgba(0,123,255,0.2) !important;
                  }
                  label.selected div:first-child { color: #007bff !important; }
                  label.selected div:nth-child(2) { color: #007bff !important; }
                </style>
              </div>
              
              <button type=\"submit\" id=\"extractBtn\">Extract</button>
              <button type=\"button\" id=\"stopBtn\" style=\"display: none; background-color: #dc3545; color: white; padding: 10px 14px; border: none; border-radius: 8px; cursor: pointer; transition: background-color 0.3s ease;\" onclick=\"stopExtraction()\">Stop</button>
            </form>
            <pre id=\"out\" hidden></pre>
          </div>

          <script>
            const form = document.getElementById('form');
            const out = document.getElementById('out');
            const extractBtn = document.getElementById('extractBtn');
            const stopBtn = document.getElementById('stopBtn');
            let currentController = null;
            
            // Handle radio button selection styling
            function updateSelection() {
              console.log('updateSelection called');
              // Remove selected class from all labels
              document.querySelectorAll('label').forEach(label => {
                label.classList.remove('selected');
              });
              // Add selected class to checked radio's label
              const checkedRadio = document.querySelector('input[name=\"llmMode\"]:checked');
              if (checkedRadio) {
                checkedRadio.closest('label').classList.add('selected');
                console.log('Selected:', checkedRadio.value);
              } else {
                console.log('No radio button checked');
              }
            }
            
            // Listen for radio button changes
            document.querySelectorAll('input[name=\"llmMode\"]').forEach(radio => {
              radio.addEventListener('change', function() {
                console.log('Radio changed to:', this.value);
                updateSelection();
              });
            });
            
            // Initialize selection on page load
            document.addEventListener('DOMContentLoaded', function() {
              console.log('DOMContentLoaded fired');
              updateSelection();
            });
            
            // Also run immediately in case DOMContentLoaded already fired
            console.log('Running updateSelection immediately');
            updateSelection();
            
            function stopExtraction() {
              if (currentController) {
                currentController.abort();
                currentController = null;
                extractBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
                out.textContent = out.textContent + '\\n\\n--- Extraction Cancelled ---\\nProcess stopped by user.';
              }
            }
            
            form.addEventListener('submit', async (e) => {
              e.preventDefault();
              const llmMode = document.querySelector('input[name=\"llmMode\"]:checked').value;
              const payload = { 
                url: form.url.value, 
                kind: form.kind.value,
                llmMode: llmMode
              };
              
              // Show stop button and hide extract button
              extractBtn.style.display = 'none';
              stopBtn.style.display = 'inline-block';
              out.hidden = false; 
              
              // Set initial loading message based on mode
              let loadingMessage = 'Loading...';
              if (llmMode === 'none') {
                loadingMessage = 'SD Processing...';
              } else if (llmMode === 'llm') {
                loadingMessage = 'LLM Processing...';
              } else if (llmMode === 'auto') {
                loadingMessage = 'SD Processing...';
              }
              
              out.textContent = loadingMessage;
              
              // Create animated dots effect
              let dotCount = 0;
              const loadingInterval = setInterval(() => {
                dotCount = (dotCount + 1) % 4;
                const dots = '.'.repeat(dotCount);
                out.textContent = loadingMessage + dots;
              }, 500);
              
              // Create abort controller for cancellation
              currentController = new AbortController();
              
              try {
                const res = await fetch('/extract', { 
                  method: 'POST', 
                  headers: { 'Content-Type': 'application/json' }, 
                  body: JSON.stringify(payload),
                  signal: currentController.signal
                });
                
                // Clear the loading animation
                clearInterval(loadingInterval);
                
                if (res.ok) {
                  const json = await res.json();
                  
                  // Separate payload from metadata
                  const meta = {
                    method: json._method_used,
                    execMs: json._execution_time,
                    llm: json._llm_usage
                  };
                  const payload = { ...json };
                  delete payload._method_used;
                  delete payload._execution_time;
                  delete payload._llm_usage;
                  
                  // Display payload only
                  let displayText = JSON.stringify(payload, null, 2);
                  
                  // Append summary with metadata
                  if (meta.method) {
                    displayText += `\\n\\n--- Extraction Summary ---\\n`;
                    displayText += `Method: ${meta.method}\\n`;
                    if (meta.execMs) {
                      displayText += `Execution time: ${meta.execMs}ms\\n`;
                    }
                    if (meta.llm) {
                      displayText += `LLM Usage: ${meta.llm.input_tokens} input + ${meta.llm.output_tokens} output = ${meta.llm.total_tokens} total tokens\\n`;
                      if (meta.llm.model) displayText += `Model: ${meta.llm.model}\\n`;
                    }
                  }
                  
                  out.textContent = displayText;
                } else {
                  out.textContent = `Error: ${res.status} ${res.statusText}`;
                }
              } catch (err) {
                // Clear the loading animation
                clearInterval(loadingInterval);
                
                if (err.name === 'AbortError') {
                  out.textContent = out.textContent + '\\n\\n--- Extraction Cancelled ---\\nProcess stopped by user.';
                } else {
                  out.textContent = String(err);
                }
              } finally {
                // Reset button states
                extractBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
                currentController = null;
              }
            });
          </script>
        </body>
        </html>
        """
    )

@app.get("/labs", response_class=HTMLResponse)
def labs():
    return (
        """
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
          <title>OmniScrape Labs</title>
          <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
              font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; 
              background: #f8fafc; 
              color: #1e293b;
            }
            .container { display: flex; min-height: 100vh; }
            
            /* Sidebar */
            .sidebar { 
              width: 280px; 
              background: white; 
              border-right: 1px solid #e2e8f0; 
              padding: 24px 0;
              position: fixed;
              height: 100vh;
              overflow-y: auto;
            }
            .sidebar-header { 
              padding: 0 24px 24px; 
              border-bottom: 1px solid #e2e8f0; 
              margin-bottom: 24px;
            }
            .sidebar h1 { font-size: 20px; font-weight: 700; margin-bottom: 8px; }
            .sidebar p { color: #64748b; font-size: 14px; }
            
            .nav-section { margin-bottom: 32px; }
            .nav-title { 
              font-size: 12px; 
              font-weight: 600; 
              color: #64748b; 
              text-transform: uppercase; 
              letter-spacing: 0.05em;
              padding: 0 24px 12px;
            }
            .nav-item { 
              display: block; 
              padding: 12px 24px; 
              color: #475569; 
              text-decoration: none; 
              border-left: 3px solid transparent;
              transition: all 0.2s;
              cursor: pointer;
            }
            .nav-item:hover { 
              background: #f1f5f9; 
              color: #1e293b;
            }
            .nav-item.active { 
              background: #eff6ff; 
              color: #2563eb; 
              border-left-color: #2563eb;
            }
            .nav-item .icon { 
              display: inline-block; 
              width: 20px; 
              margin-right: 12px; 
              text-align: center;
            }
            
            /* Main Content */
            .main-content { 
              flex: 1; 
              margin-left: 280px; 
              padding: 32px;
            }
            .content-header { 
              margin-bottom: 32px; 
              padding-bottom: 24px; 
              border-bottom: 1px solid #e2e8f0;
            }
            .content-header h2 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
            .content-header p { color: #64748b; font-size: 16px; }
            
            /* Graph Content */
            .graph-content { display: none; }
            .graph-content.active { display: block; }
            
            .graph-card { 
              background: white; 
              border: 1px solid #e2e8f0; 
              border-radius: 12px; 
              padding: 24px; 
              margin-bottom: 24px;
            }
            .graph-card h3 { 
              font-size: 18px; 
              font-weight: 600; 
              margin-bottom: 8px; 
              color: #1e293b;
            }
            .graph-card p { 
              color: #64748b; 
              margin-bottom: 20px; 
              line-height: 1.6;
            }
            
            /* Form Elements */
            .form-group { margin-bottom: 20px; }
            .form-group label { 
              display: block; 
              font-weight: 600; 
              margin-bottom: 8px; 
              color: #374151;
            }
            .form-group input, 
            .form-group textarea, 
            .form-group select { 
              width: 100%; 
              padding: 12px; 
              border: 1px solid #d1d5db; 
              border-radius: 8px; 
              font-size: 14px;
              transition: border-color 0.2s;
            }
            .form-group input:focus, 
            .form-group textarea:focus, 
            .form-group select:focus { 
              outline: none; 
              border-color: #2563eb; 
              box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
            }
            .form-group textarea { 
              resize: vertical; 
              min-height: 80px;
            }
            
            /* Buttons */
            .btn { 
              background: #2563eb; 
              color: white; 
              border: none; 
              padding: 12px 24px; 
              border-radius: 8px; 
              font-weight: 600; 
              cursor: pointer; 
              transition: background-color 0.2s;
            }
            .btn:hover { background: #1d4ed8; }
            .btn:disabled { 
              background: #9ca3af; 
              cursor: not-allowed;
            }
            
            /* Results */
            .result { 
              margin-top: 20px; 
              padding: 16px; 
              background: #f8fafc; 
              border: 1px solid #e2e8f0; 
              border-radius: 8px; 
              font-family: 'Monaco', 'Menlo', monospace; 
              font-size: 13px; 
              white-space: pre-wrap; 
              max-height: 400px; 
              overflow-y: auto;
            }
            .result.loading { 
              color: #64748b; 
              font-style: italic;
            }
            .result.error { 
              background: #fef2f2; 
              border-color: #fecaca; 
              color: #dc2626;
            }
            .result.success { 
              background: #f0fdf4; 
              border-color: #bbf7d0; 
              color: #166534;
            }
            
            /* Status Indicators */
            .status-indicator { 
              display: inline-block; 
              width: 8px; 
              height: 8px; 
              border-radius: 50%; 
              margin-right: 8px;
            }
            .status-indicator.ready { background: #10b981; }
            .status-indicator.loading { background: #f59e0b; }
            .status-indicator.error { background: #ef4444; }
            
            /* Responsive */
            @media (max-width: 768px) {
              .sidebar { 
                transform: translateX(-100%); 
                transition: transform 0.3s;
              }
              .sidebar.open { transform: translateX(0); }
              .main-content { margin-left: 0; }
            }
            
            /* Welcome Screen */
            .welcome-screen {
              text-align: center;
              padding: 60px 20px;
            }
            .welcome-screen h2 {
              font-size: 32px;
              margin-bottom: 16px;
              color: #1e293b;
            }
            .welcome-screen p {
              font-size: 18px;
              color: #64748b;
              margin-bottom: 32px;
              max-width: 600px;
              margin-left: auto;
              margin-right: auto;
            }
            .feature-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
              gap: 24px;
              margin-top: 40px;
            }
            .feature-card {
              background: white;
              padding: 24px;
              border-radius: 12px;
              border: 1px solid #e2e8f0;
              text-align: left;
            }
            .feature-card h3 {
              font-size: 16px;
              font-weight: 600;
              margin-bottom: 8px;
              color: #1e293b;
            }
            .feature-card p {
              font-size: 14px;
              color: #64748b;
              line-height: 1.5;
            }
          </style>
        </head>
        <body>
          <div class=\"container\">
            <!-- Sidebar -->
            <div class=\"sidebar\">
              <div class=\"sidebar-header\">
                <h1>🧪 Labs</h1>
                <p>Interactive ScrapeGraphAI Testing</p>
              </div>
              
              <div class=\"nav-section\">
                <div class=\"nav-title\">Single Page</div>
                <div class=\"nav-item active\" onclick=\"showGraph('smart')\">
                  <span class=\"icon\">🎯</span>SmartScraper
                </div>
                <div class=\"nav-item\" onclick=\"showGraph('speech')\">
                  <span class=\"icon\">🔊</span>SpeechGraph
                </div>
                <div class=\"nav-item\" onclick=\"showGraph('script')\">
                  <span class=\"icon\">📝</span>ScriptCreator
                </div>
              </div>
              
              <div class=\"nav-section\">
                <div class=\"nav-title\">Multi Page</div>
                <div class=\"nav-item\" onclick=\"showGraph('search')\">
                  <span class=\"icon\">🔍</span>SearchGraph
                </div>
                <div class=\"nav-item\" onclick=\"showGraph('multi')\">
                  <span class=\"icon\">📄</span>SmartScraperMulti
                </div>
                <div class=\"nav-item\" onclick=\"showGraph('script-multi')\">
                  <span class=\"icon\">📚</span>ScriptCreatorMulti
                </div>
              </div>
              
              <div class=\"nav-section\">
                <div class=\"nav-title\">Navigation</div>
                <a href=\"/\" class=\"nav-item\">
                  <span class=\"icon\">🏠</span>Home
                </a>
                <a href=\"/docs\" class=\"nav-item\">
                  <span class=\"icon\">📖</span>API Docs
                </a>
                <a href=\"/health\" class=\"nav-item\">
                  <span class=\"icon\">❤️</span>Health Check
                </a>
              </div>
            </div>
            
            <!-- Main Content -->
            <div class=\"main-content\">
              <div class=\"content-header\">
                <h2>ScrapeGraphAI Labs</h2>
                <p>Test and experiment with different ScrapeGraphAI graph types for web scraping and data extraction.</p>
              </div>
              
              <!-- Welcome Screen -->
              <div id=\"welcome\" class=\"welcome-screen\">
                <h2>Welcome to OmniScrape Labs</h2>
                <p>Select a graph type from the sidebar to start experimenting with ScrapeGraphAI capabilities.</p>
                
                <div class=\"feature-grid\">
                  <div class=\"feature-card\">
                    <h3>🎯 SmartScraper</h3>
                    <p>Single-page extraction with custom prompts. Perfect for articles, products, and structured content.</p>
                  </div>
                  <div class=\"feature-card\">
                    <h3>🔍 SearchGraph</h3>
                    <p>Multi-page extraction using search engine results. Great for research and competitive analysis.</p>
                  </div>
                  <div class=\"feature-card\">
                    <h3>🔊 SpeechGraph</h3>
                    <p>Convert web content to audio. Ideal for accessibility and podcast content generation.</p>
                  </div>
                  <div class=\"feature-card\">
                    <h3>📝 ScriptCreator</h3>
                    <p>Generate Python scraping scripts automatically. Perfect for learning and rapid prototyping.</p>
                  </div>
                  <div class=\"feature-card\">
                    <h3>📄 Multi-Page</h3>
                    <p>Process multiple URLs with a single prompt. Excellent for batch processing and data aggregation.</p>
                  </div>
                  <div class=\"feature-card\">
                    <h3>⚡ Real-time Results</h3>
                    <p>See token usage, execution time, and detailed results instantly. Monitor performance and costs.</p>
                  </div>
                </div>
              </div>
              
              <!-- SmartScraperGraph -->
              <div id=\"smart\" class=\"graph-content\">
                <div class=\"graph-card\">
                  <h3>🎯 SmartScraperGraph</h3>
                  <p>Single-page scraper that only needs a user prompt and an input source. Perfect for extracting articles, products, or any structured content from a single webpage.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"smart-url\">URL</label>
                    <input type=\"text\" id=\"smart-url\" placeholder=\"Enter URL\" value=\"https://httpbin.org/html\">
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"smart-prompt\">Extraction Prompt</label>
                    <textarea id=\"smart-prompt\" placeholder=\"Enter your extraction prompt\" rows=\"3\">Extract the main title, author, and key points from this article</textarea>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runGraph('smart')\">
                    <span class=\"status-indicator ready\"></span>Run SmartScraper
                  </button>
                  
                  <div id=\"smart-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- SearchGraph -->
              <div id=\"search\" class=\"graph-content\">
                <div class=\"graph-card\">
                  <h3>🔍 SearchGraph</h3>
                  <p>Multi-page scraper that extracts information from the top n search results of a search engine. Requires Bing Search API key.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"search-query\">Search Query</label>
                    <input type=\"text\" id=\"search-query\" placeholder=\"Enter search query\" value=\"artificial intelligence news\">
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"search-count\">Number of Results</label>
                    <input type=\"number\" id=\"search-count\" placeholder=\"Number of results\" value=\"3\" min=\"1\" max=\"10\">
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"search-prompt\">Extraction Prompt</label>
                    <textarea id=\"search-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Extract the title, summary, and publication date from each article</textarea>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runGraph('search')\">
                    <span class=\"status-indicator ready\"></span>Run SearchGraph
                  </button>
                  
                  <div id=\"search-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- SpeechGraph -->
              <div id=\"speech\" class=\"graph-content\">
                <div class=\"graph-card\">
                  <h3>🔊 SpeechGraph</h3>
                  <p>Single-page scraper that extracts information from a website and generates an audio file. Perfect for accessibility and content consumption.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"speech-url\">URL</label>
                    <input type=\"text\" id=\"speech-url\" placeholder=\"Enter URL\" value=\"https://httpbin.org/html\">
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"speech-prompt\">Extraction Prompt</label>
                    <textarea id=\"speech-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Extract the main content and convert it to speech</textarea>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runGraph('speech')\">
                    <span class=\"status-indicator ready\"></span>Run SpeechGraph
                  </button>
                  
                  <div id=\"speech-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- ScriptCreatorGraph -->
              <div id=\"script\" class=\"graph-content\">
                <div class=\"graph-card\">
                  <h3>📝 ScriptCreatorGraph</h3>
                  <p>Single-page scraper that extracts information from a website and generates a Python script. Great for learning and automation.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"script-url\">URL</label>
                    <input type=\"text\" id=\"script-url\" placeholder=\"Enter URL\" value=\"https://httpbin.org/html\">
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"script-prompt\">Extraction Prompt</label>
                    <textarea id=\"script-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Create a Python script to extract product information from this page</textarea>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runGraph('script')\">
                    <span class=\"status-indicator ready\"></span>Run ScriptCreator
                  </button>
                  
                  <div id=\"script-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- SmartScraperMultiGraph -->
              <div id=\"multi\" class=\"graph-content\">
                <div class=\"graph-card\">
                  <h3>📄 SmartScraperMultiGraph</h3>
                  <p>Multi-page scraper that extracts information from multiple pages given a single prompt and a list of sources. Perfect for batch processing.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"multi-urls\">URLs (one per line)</label>
                    <textarea id=\"multi-urls\" placeholder=\"Enter URLs (one per line)\" rows=\"3\">https://httpbin.org/html
https://httpbin.org/json
https://example.com</textarea>
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"multi-prompt\">Extraction Prompt</label>
                    <textarea id=\"multi-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Extract the title and main content from each page</textarea>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runGraph('multi')\">
                    <span class=\"status-indicator ready\"></span>Run SmartScraperMulti
                  </button>
                  
                  <div id=\"multi-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- ScriptCreatorMultiGraph -->
              <div id=\"script-multi\" class=\"graph-content\">
                <div class=\"graph-card\">
                  <h3>📚 ScriptCreatorMultiGraph</h3>
                  <p>Multi-page scraper that generates a Python script for extracting information from multiple pages and sources. Ideal for complex automation tasks.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"script-multi-urls\">URLs (one per line)</label>
                    <textarea id=\"script-multi-urls\" placeholder=\"Enter URLs (one per line)\" rows=\"3\">https://httpbin.org/html
https://httpbin.org/json</textarea>
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"script-multi-prompt\">Extraction Prompt</label>
                    <textarea id=\"script-multi-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Create a Python script to extract structured data from these pages</textarea>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runGraph('script-multi')\">
                    <span class=\"status-indicator ready\"></span>Run ScriptCreatorMulti
                  </button>
                  
                  <div id=\"script-multi-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
            </div>
          </div>

          <script>
            let currentGraph = null;
            
            function showGraph(graphType) {
              // Hide welcome screen
              document.getElementById('welcome').style.display = 'none';
              
              // Hide all graph contents
              document.querySelectorAll('.graph-content').forEach(content => {
                content.classList.remove('active');
              });
              
              // Remove active class from all nav items
              document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.remove('active');
              });
              
              // Show selected graph content
              document.getElementById(graphType).classList.add('active');
              
              // Add active class to clicked nav item
              event.target.classList.add('active');
              
              currentGraph = graphType;
            }
            
            async function runGraph(graphType) {
              const resultDiv = document.getElementById(graphType + '-result');
              const button = event.target;
              const statusIndicator = button.querySelector('.status-indicator');
              
              // Show result div and set loading state
              resultDiv.style.display = 'block';
              resultDiv.textContent = 'Loading...';
              resultDiv.className = 'result loading';
              button.disabled = true;
              statusIndicator.className = 'status-indicator loading';
              
              try {
                let data = {};
                
                // Collect data based on graph type
                switch(graphType) {
                  case 'smart':
                    data = {
                      url: document.getElementById('smart-url').value,
                      prompt: document.getElementById('smart-prompt').value
                    };
                    break;
                  case 'search':
                    data = {
                      query: document.getElementById('search-query').value,
                      count: parseInt(document.getElementById('search-count').value),
                      prompt: document.getElementById('search-prompt').value
                    };
                    break;
                  case 'speech':
                    data = {
                      url: document.getElementById('speech-url').value,
                      prompt: document.getElementById('speech-prompt').value
                    };
                    break;
                  case 'script':
                    data = {
                      url: document.getElementById('script-url').value,
                      prompt: document.getElementById('script-prompt').value
                    };
                    break;
                  case 'multi':
                    data = {
                      urls: document.getElementById('multi-urls').value.split('\\n').filter(u => u.trim()),
                      prompt: document.getElementById('multi-prompt').value
                    };
                    break;
                  case 'script-multi':
                    data = {
                      urls: document.getElementById('script-multi-urls').value.split('\\n').filter(u => u.trim()),
                      prompt: document.getElementById('script-multi-prompt').value
                    };
                    break;
                }
                
                const response = await fetch('/labs/' + graphType, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                  resultDiv.textContent = JSON.stringify(result.data, null, 2);
                  resultDiv.className = 'result success';
                  statusIndicator.className = 'status-indicator ready';
                } else {
                  resultDiv.textContent = 'Error: ' + result.error;
                  resultDiv.className = 'result error';
                  statusIndicator.className = 'status-indicator error';
                }
              } catch (error) {
                resultDiv.textContent = 'Error: ' + error.message;
                resultDiv.className = 'result error';
                statusIndicator.className = 'status-indicator error';
              } finally {
                button.disabled = false;
              }
            }
          </script>
        </body>
        </html>
        """
    )

# Labs API endpoints
@app.post("/labs/smart", tags=["labs"], summary="SmartScraperGraph", description="Single-page scraper with custom prompts")
async def labs_smart(request: Request):
    try:
        data = await request.json()
        url = data.get("url")
        prompt = data.get("prompt")
        
        if not url or not prompt:
            return {"success": False, "error": "URL and prompt are required"}
        
        # Use SmartScraperGraph
        from .labs_graphs import run_graph_async, run_smart_scraper
        result = await run_graph_async(run_smart_scraper, url, prompt)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/labs/search", tags=["labs"], summary="SearchGraph", description="Multi-page scraper using search engine results (requires Bing API)")
async def labs_search(request: Request):
    try:
        data = await request.json()
        query = data.get("query")
        count = data.get("count", 3)
        prompt = data.get("prompt")
        
        if not query or not prompt:
            return {"success": False, "error": "Query and prompt are required"}
        
        # Use SearchGraph (requires Bing API key)
        from .labs_graphs import run_graph_async, run_search_graph
        result = await run_graph_async(run_search_graph, query, count, prompt)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/labs/speech", tags=["labs"], summary="SpeechGraph", description="Audio generation from web content")
async def labs_speech(request: Request):
    try:
        data = await request.json()
        url = data.get("url")
        prompt = data.get("prompt")
        
        if not url or not prompt:
            return {"success": False, "error": "URL and prompt are required"}
        
        # Use SpeechGraph
        from .labs_graphs import run_graph_async, run_speech_graph
        result = await run_graph_async(run_speech_graph, url, prompt)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/labs/script", tags=["labs"], summary="ScriptCreatorGraph", description="Python script generation for web scraping")
async def labs_script(request: Request):
    try:
        data = await request.json()
        url = data.get("url")
        prompt = data.get("prompt")
        
        if not url or not prompt:
            return {"success": False, "error": "URL and prompt are required"}
        
        # Use ScriptCreatorGraph
        from .labs_graphs import run_graph_async, run_script_creator
        result = await run_graph_async(run_script_creator, url, prompt)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/labs/multi", tags=["labs"], summary="SmartScraperMultiGraph", description="Multi-page extraction with single prompt")
async def labs_multi(request: Request):
    try:
        data = await request.json()
        urls = data.get("urls", [])
        prompt = data.get("prompt")
        
        if not urls or not prompt:
            return {"success": False, "error": "URLs and prompt are required"}
        
        # Use SmartScraperMultiGraph
        from .labs_graphs import run_graph_async, run_smart_scraper_multi
        result = await run_graph_async(run_smart_scraper_multi, urls, prompt)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/labs/script-multi", tags=["labs"], summary="ScriptCreatorMultiGraph", description="Multi-page Python script generation")
async def labs_script_multi(request: Request):
    try:
        data = await request.json()
        urls = data.get("urls", [])
        prompt = data.get("prompt")
        
        if not urls or not prompt:
            return {"success": False, "error": "URLs and prompt are required"}
        
        # Use ScriptCreatorMultiGraph
        from .labs_graphs import run_graph_async, run_script_creator_multi
        result = await run_graph_async(run_script_creator_multi, urls, prompt)
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/health", tags=["health"], summary="Health Check", description="Comprehensive health check including service status, dependencies, and system metrics")
def health(): 
    import os
    import time
    import psutil
    from datetime import datetime
    
    # Basic service status
    status = "healthy"
    checks = {}
    
    # Check OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    checks["openai_api"] = {
        "status": "configured" if openai_key else "missing",
        "message": "OpenAI API key is configured" if openai_key else "OpenAI API key is missing"
    }
    
    # Check Bing Search API key (optional)
    bing_key = os.getenv("BING_SEARCH_API_KEY")
    checks["bing_api"] = {
        "status": "configured" if bing_key else "not_configured",
        "message": "Bing Search API key is configured" if bing_key else "Bing Search API key not configured (optional)"
    }
    
    # Check model configuration
    model = os.getenv("SCRAPEGRAPH_MODEL", "gpt-4o-mini")
    checks["model_config"] = {
        "status": "configured",
        "message": f"Model configured: {model}"
    }
    
    # System metrics
    try:
        process = psutil.Process()
        checks["system"] = {
            "status": "healthy",
            "cpu_percent": process.cpu_percent(),
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "uptime_seconds": round(time.time() - process.create_time(), 2)
        }
    except Exception as e:
        checks["system"] = {
            "status": "error",
            "message": f"Could not retrieve system metrics: {str(e)}"
        }
    
    # Check if any critical components are missing
    critical_failed = any(
        check["status"] in ["missing", "error"] 
        for name, check in checks.items() 
        if name in ["openai_api"]
    )
    
    if critical_failed:
        status = "degraded"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "service": "OmniScrape API",
        "version": "0.1.0",
        "checks": checks,
        "endpoints": {
            "main_api": "/extract",
            "labs": "/labs",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "features": {
            "extraction_methods": ["structured_data", "readability", "llm_fallback"],
            "labs_graphs": ["smart", "search", "speech", "script", "multi", "script-multi"],
            "supported_content": ["articles", "products"]
        }
    }

@app.post("/extract", tags=["extraction"], summary="Extract Article or Product", description="Extract structured data from articles or products using cascading fallback strategy")
async def do_extract(req: ExtractRequest, request: Request):
    try:
        # Check if client disconnected
        if await request.is_disconnected():
            return {"error": "Client disconnected"}
        
        data = await extract(str(req.url), req.kind, req.llmMode)
        return data
    except asyncio.CancelledError:
        # Handle cancellation
        return {"error": "Extraction cancelled", "cancelled": True}
    except Exception as e:
        # Surface backend error details to the client
        import traceback
        tb = traceback.format_exc()
        # Limit trace size to avoid huge responses
        short_tb = tb[-4000:]
        return JSONResponse(status_code=500, content={"error": str(e), "trace": short_tb})
