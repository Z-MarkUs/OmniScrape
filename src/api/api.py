from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Literal
import orjson
import asyncio
from datetime import datetime
from src.core.pipeline import extract
from src.crawlers.article_crawler import crawl_with_full_content

class ExtractRequest(BaseModel):
    url: HttpUrl
    kind: Literal["article", "product"]
    llmMode: Literal["none", "llm", "auto"] = "auto"

class MonitorRequest(BaseModel):
    url: HttpUrl
    mode: Literal["sd", "llm", "auto"] = "auto"

class CrawlRequest(BaseModel):
    url: HttpUrl
    count: int = 10
    crawlMode: Literal["sd", "llm", "auto"] = "auto"

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
          <title>OmniScrape - Universal Web Scraping Platform</title>
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
              transform: translateX(-100%);
              transition: transform 0.3s ease;
              z-index: 1000;
            }
            .sidebar.open { 
              transform: translateX(0); 
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
              color: #4285f4; 
              border-left-color: #4285f4;
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
              padding: 32px;
              transition: margin-left 0.3s ease;
            }
            .content-header { 
              margin-bottom: 32px; 
              padding-bottom: 24px; 
              border-bottom: 1px solid #e2e8f0;
            }
            .content-header h2 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
            .content-header p { color: #64748b; font-size: 16px; }
            
            /* Function Cards */
            .function-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
              gap: 24px;
              margin-top: 32px;
            }
            .function-card {
              background: white;
              border: 1px solid #e2e8f0;
              border-radius: 12px;
              padding: 24px;
              transition: all 0.2s;
              cursor: pointer;
            }
            .function-card:hover {
              border-color: #4285f4;
              box-shadow: 0 4px 12px rgba(66, 133, 244, 0.1);
            }
            .function-card h3 {
              font-size: 18px;
              font-weight: 600;
              margin-bottom: 8px;
              color: #1e293b;
            }
            .function-card p {
              color: #64748b;
              margin-bottom: 16px;
              line-height: 1.5;
            }
            .function-card .icon {
              font-size: 24px;
              margin-bottom: 12px;
              display: block;
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
              border-color: #4285f4; 
              box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.1);
            }
            
            /* Buttons */
            .btn { 
              background: #4285f4; 
              color: white; 
              border: none; 
              padding: 12px 24px; 
              border-radius: 8px; 
              font-weight: 600; 
              cursor: pointer; 
              transition: background-color 0.2s;
              width: 100%;
            }
            .btn:hover { background: #3367d6; }
            .btn:disabled { 
              background: #9ca3af; 
              cursor: not-allowed;
            }
            .btn-danger { background: #ea4335; }
            .btn-danger:hover { background: #d33b2c; }
            
            .menu-toggle {
              position: fixed;
              top: 20px;
              right: 20px;
              left: auto;
              background: #4285f4;
              color: white;
              border: none;
              padding: 12px;
              border-radius: 8px;
              cursor: pointer;
              z-index: 1001;
              font-size: 16px;
              box-shadow: 0 2px 8px rgba(66, 133, 244, 0.3);
            }
            .menu-toggle:hover {
              background: #3367d6;
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
            
            /* Mode Selection */
            .mode-selection { display: flex; gap: 12px; margin: 16px 0; }
            .mode-option { 
              flex: 1; 
              border: 2px solid #e5e7eb; 
              border-radius: 8px; 
              padding: 16px; 
              cursor: pointer; 
              transition: all 0.2s;
              text-align: center;
              background: white;
            }
            .mode-option:hover { 
              border-color: #4285f4; 
              transform: translateY(-2px); 
              box-shadow: 0 4px 12px rgba(66, 133, 244, 0.15);
            }
            .mode-option.active { 
              border-color: #4285f4; 
              background: #f8f9ff; 
              box-shadow: 0 4px 12px rgba(66, 133, 244, 0.2);
            }
            .mode-option input[type=\"radio\"] { display: none; }
            .mode-option label { 
              display: block; 
              font-weight: 700; 
              font-size: 16px; 
              margin-bottom: 4px;
              cursor: pointer;
              color: #495057;
            }
            .mode-desc { 
              font-size: 12px; 
              color: #6c757d; 
              display: block;
              line-height: 1.3;
            }
            /* Google color accents per option (default state) */
            .mode-option.sd label { color: #34a853; }   /* Google Green */
            .mode-option.llm label { color: #ea4335; }  /* Google Red */
            .mode-option.auto label { color: #fbbc05; } /* Google Amber */
            .mode-option.active label { 
              color: #4285f4; 
            }
            
            /* Responsive */
            @media (max-width: 768px) {
              .sidebar { 
                transform: translateX(-100%); 
                transition: transform 0.3s;
              }
              .sidebar.open { transform: translateX(0); }
              .main-content { margin-left: 0; }
            }

            /* When sidebar is open on larger screens, shift content */
            @media (min-width: 769px) {
              .sidebar.open ~ .main-content { margin-left: 280px; }
            }
          </style>
        </head>
        <body>
          <button class=\"menu-toggle\" onclick=\"toggleSidebar()\">☰</button>
          <div class=\"container\">
            <!-- Sidebar -->
            <div class=\"sidebar\">
              <div class=\"sidebar-header\">
                <h1>OmniScrape</h1>
                <p>Advanced Web Scraping Platform</p>
          </div>

              <div class=\"nav-section\">
                <div class=\"nav-title\">Navigation</div>
                <div class=\"nav-item active\" onclick=\"showSection('home', this)\">Home</div>
              </div>

              <div class=\"nav-section\">
                <div class=\"nav-title\">Main Functions</div>
                <div class=\"nav-item\" onclick=\"showSection('monitor', this)\">Monitor All Articles</div>
                <div class=\"nav-item\" onclick=\"showSection('extract', this)\">Extract Single Article</div>
                <div class=\"nav-item\" onclick=\"showSection('crawler', this)\">Article Crawler</div>
              </div>
              
              <div class=\"nav-section\">
                <div class=\"nav-title\">Advanced</div>
                <div class=\"nav-item\" onclick=\"showSection('smartscraper', this)\">SmartScraper</div>
                <div class=\"nav-item\" onclick=\"showSection('searchgraph', this)\">SearchGraph</div>
                <div class=\"nav-item\" onclick=\"showSection('multigraph', this)\">MultiGraph</div>
              </div>
              
              <div class=\"nav-section\">
                <div class=\"nav-title\">Documentation</div>
                <a href=\"/docs\" class=\"nav-item\">API Documentation</a>
                <a href=\"/redoc\" class=\"nav-item\">ReDoc</a>
                <a href=\"/health\" class=\"nav-item\">Health Check</a>
              </div>
            </div>
            
            <!-- Main Content -->
            <div class=\"main-content\">
              <!-- Home Section -->
              <div id=\"home\" class=\"content-section\">
                <div class=\"content-header\">
                  <h2>Welcome to OmniScrape</h2>
                  <p>Advanced web scraping platform with intelligent content extraction, comprehensive monitoring capabilities, and AI-powered analysis tools for modern data collection needs.</p>
                </div>
                
                <div class=\"function-grid\">
                  <div class=\"function-card\" onclick=\"showSection('monitor', this)\">
                    <h3>Monitor All Articles</h3>
                    <p>Fast article list monitoring and metadata extraction. Scans article list pages to extract article titles, URLs, publication dates, and authors without fetching full content. Perfect for content monitoring and discovery.</p>
                  </div>
                  
                  <div class=\"function-card\" onclick=\"showSection('extract', this)\">
                    <h3>Extract Single Article</h3>
                    <p>Precision extraction from individual article URLs. Leverages structured data parsing, AI-powered content recognition, and intelligent fallback strategies to ensure maximum accuracy and completeness.</p>
                  </div>
                  
                  <div class=\"function-card\" onclick=\"showSection('crawler', this)\">
                    <h3>Article Crawler</h3>
                    <p>Comprehensive article crawling with full content extraction. First extracts article lists from list pages, then crawls each individual article to retrieve complete content including full text, metadata, and publication details.</p>
                  </div>
                  
                  <div class=\"function-card\" onclick=\"showSection('smartscraper', this)\">
                    <h3>ScrapeGraphAI Labs</h3>
                    <p>Advanced experimentation platform for ScrapeGraphAI capabilities. Test SmartScraper, SearchGraph, SpeechGraph, and ScriptCreator graphs with real-time results and comprehensive analysis tools.</p>
                  </div>
                  
                  <div class=\"function-card\" onclick=\"window.open('/docs', '_blank')\">
                    <h3>API Documentation</h3>
                    <p>Complete API reference with interactive documentation. Explore all endpoints, parameters, and response formats.</p>
                  </div>
                </div>
              </div>
              
              <!-- Monitor Section -->
              <div id=\"monitor\" class=\"content-section\" style=\"display:none;\">
                <div class=\"content-header\">
                  <h2>Monitor All Articles</h2>
                  <p>Fast article list monitoring and metadata extraction. Scans article list pages to extract article titles, URLs, publication dates, and authors without fetching full content. Perfect for content monitoring and discovery.</p>
                </div>
                
                <div class=\"function-card\">
                  <h3>Article List Monitor</h3>
                  <p>Fast and efficient article list scanning. Extracts article metadata (titles, URLs, dates, authors) from list pages without downloading full content. Ideal for content discovery, monitoring, and quick analysis.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"monitor-url\">Article List URL</label>
                    <input type=\"text\" id=\"monitor-url\" placeholder=\"Enter article list URL\" value=\"https://column.etnetchina.cn/list/article-latest\">
                  </div>
                  
                  <div class=\"mode-selection\">
                    <div class=\"mode-option sd\" onclick=\"selectMonitorMode('sd')\">
                      <input type=\"radio\" name=\"monitorMode\" value=\"sd\" id=\"monitor-mode-sd\">
                      <label for=\"monitor-mode-sd\">SD</label>
                      <span class=\"mode-desc\">Structured Data + Pattern Recognition</span>
                    </div>
                    <div class=\"mode-option llm\" onclick=\"selectMonitorMode('llm')\">
                      <input type=\"radio\" name=\"monitorMode\" value=\"llm\" id=\"monitor-mode-llm\">
                      <label for=\"monitor-mode-llm\">LLM</label>
                      <span class=\"mode-desc\">AI-Powered Content Recognition</span>
                    </div>
                    <div class=\"mode-option auto active\" onclick=\"selectMonitorMode('auto')\">
                      <input type=\"radio\" name=\"monitorMode\" value=\"auto\" id=\"monitor-mode-auto\" checked>
                      <label for=\"monitor-mode-auto\">AUTO</label>
                      <span class=\"mode-desc\">Intelligent Cascading Strategy</span>
                    </div>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runMonitor()\">Monitor All Articles</button>
                  <div id=\"monitor-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- Extract Section -->
              <div id=\"extract\" class=\"content-section\" style=\"display:none;\">
                <div class=\"content-header\">
                  <h2>Extract Single Article</h2>
                  <p>Precision content extraction from individual article URLs. Utilizes advanced parsing techniques, structured data recognition, and AI-powered content analysis for maximum accuracy and completeness.</p>
                </div>
                
                <div class=\"function-card\">
                  <h3>Article Extraction</h3>
                  <p>Advanced single-article content extraction with intelligent parsing capabilities. Supports multiple extraction strategies including structured data parsing, AI-powered content recognition, and hybrid approaches for optimal results.</p>
                  
                  <div class=\"form-group\">
                    <label for=\"extract-url\">Article URL</label>
                    <input type=\"text\" id=\"extract-url\" placeholder=\"Enter article URL\" value=\"https://httpbin.org/html\">
                  </div>
                  
                  <div class=\"form-group\">
                    <label for=\"extract-kind\">Content Type</label>
                    <select id=\"extract-kind\">
                      <option value=\"article\">Article</option>
                      <option value=\"product\">Product</option>
              </select>
                  </div>
                  
                  <div class=\"mode-selection\">
                    <div class=\"mode-option sd\" onclick=\"selectExtractMode('none')\">
                      <input type=\"radio\" name=\"extractMode\" value=\"none\" id=\"extract-mode-none\">
                      <label for=\"extract-mode-none\">SD</label>
                      <span class=\"mode-desc\">Pure Structured Data Parsing</span>
                    </div>
                    <div class=\"mode-option llm\" onclick=\"selectExtractMode('llm')\">
                      <input type=\"radio\" name=\"extractMode\" value=\"llm\" id=\"extract-mode-llm\">
                      <label for=\"extract-mode-llm\">LLM</label>
                      <span class=\"mode-desc\">AI-Powered Extraction</span>
                    </div>
                    <div class=\"mode-option auto active\" onclick=\"selectExtractMode('auto')\">
                      <input type=\"radio\" name=\"extractMode\" value=\"auto\" id=\"extract-mode-auto\" checked>
                      <label for=\"extract-mode-auto\">AUTO</label>
                      <span class=\"mode-desc\">Intelligent Cascading Strategy</span>
                    </div>
                  </div>
                  
                  <button class=\"btn\" onclick=\"runExtract()\">Extract Article</button>
                  <div id=\"extract-result\" class=\"result\" style=\"display:none;\"></div>
                </div>
              </div>
              
              <!-- Auto Section (Removed) -->
              
              
              <!-- SmartScraper Section -->
              <div id="smartscraper" class="content-section" style="display:none;">
                <div class="content-header">
                  <h2>SmartScraper</h2>
                  <p>Intelligent single-page content extraction with custom prompts. Leverages AI-powered content recognition to extract specific data points from web pages based on natural language instructions.</p>
                </div>
                
                <div class="function-card">
                  <h3>SmartScraperGraph</h3>
                  <p>Advanced single-page content extraction with AI-powered analysis. Process any web page with custom prompts to extract structured data, specific information, or perform content analysis tasks.</p>
                  
                  <div class="form-group">
                    <label for="smart-url">Target URL</label>
                    <input type="text" id="smart-url" placeholder="Enter URL to scrape" value="https://httpbin.org/html">
                  </div>
                  
                  <div class="form-group">
                    <label for="smart-prompt">Extraction Prompt</label>
                    <textarea id="smart-prompt" rows="4" placeholder="Describe what you want to extract...">Extract the main title, content summary, and any key information from this page</textarea>
                  </div>
                  
                  <button class="btn" onclick="runSmartScraper()">Run SmartScraper</button>
                  <div id="smart-result" class="result" style="display:none;"></div>
                </div>
              </div>
              
              <!-- SearchGraph Section -->
              <div id="searchgraph" class="content-section" style="display:none;">
                <div class="content-header">
                  <h2>SearchGraph</h2>
                  <p>Advanced search result processing with AI-powered extraction. Processes multiple search results simultaneously, extracting structured data from top-ranked pages based on custom prompts and requirements.</p>
                </div>
                
                <div class="function-card">
                  <h3>SearchGraph Processing</h3>
                  <p>Intelligent search result analysis and content extraction. Automatically processes multiple search results to extract relevant information, compare content, and perform comprehensive analysis across multiple sources.</p>
                  
                  <div class="form-group">
                    <label for="search-query">Search Query</label>
                    <input type="text" id="search-query" placeholder="Enter search query" value="artificial intelligence news">
                  </div>
                  
                  <div class="form-group">
                    <label for="search-count">Number of Results (1-10)</label>
                    <input type="number" id="search-count" placeholder="Number of results to process" value="3" min="1" max="10">
                  </div>
                  
                  <div class="form-group">
                    <label for="search-prompt">Extraction Prompt</label>
                    <textarea id="search-prompt" rows="4" placeholder="Describe what to extract from each result...">Extract the title, summary, publication date, and main topics from each search result</textarea>
                  </div>
                  
                  <button class="btn" onclick="runSearchGraph()">Run SearchGraph</button>
                  <div id="search-result" class="result" style="display:none;"></div>
                </div>
              </div>
              
              <!-- MultiGraph Section -->
              <div id="multigraph" class="content-section" style="display:none;">
                <div class="content-header">
                  <h2>MultiGraph</h2>
                  <p>Multi-page content extraction with unified processing. Efficiently processes multiple URLs simultaneously using a single prompt, ideal for batch content analysis and comparative studies.</p>
                </div>
                
                <div class="function-card">
                  <h3>SmartScraperMultiGraph</h3>
                  <p>Batch processing for multiple web pages with consistent extraction criteria. Perfect for comparative analysis, content auditing, and large-scale data collection projects.</p>
                  
                  <div class="form-group">
                    <label for="multi-urls">URLs to Process (one per line)</label>
                    <textarea id="multi-urls" rows="5" placeholder="Enter URLs, one per line...">https://httpbin.org/html
https://example.com
https://httpbin.org/json</textarea>
                  </div>
                  
                  <div class="form-group">
                    <label for="multi-prompt">Extraction Prompt</label>
                    <textarea id="multi-prompt" rows="4" placeholder="Describe what to extract from each URL...">Extract the main title, content summary, and key information from each page</textarea>
                  </div>
                  
                  <button class="btn" onclick="runMultiGraph()">Run MultiGraph</button>
                  <div id="multi-result" class="result" style="display:none;"></div>
                </div>
              </div>
              
              <!-- Crawler Section (inline) -->
              <div id="crawler" class="content-section" style="display:none;">
                <div class="content-header">
                  <h2>Article Crawler</h2>
                  <p>Comprehensive article crawling with full content extraction. First extracts article lists from list pages, then crawls each individual article to retrieve complete content including full text, metadata, and publication details.</p>
                </div>
                
                <div class="function-card">
                  <h3>Universal Article Crawler</h3>
                  <p>Complete article crawling with full content extraction. Extracts article lists from list pages, then individually crawls each article to retrieve full content, metadata, and publication details. Perfect for comprehensive content analysis and research.</p>
                  
                  <div class="form-group">
                    <label for="crawler-url">Article List URL</label>
                    <input type="text" id="crawler-url" placeholder="Enter article list URL" value="https://column.etnetchina.cn/list/article-latest">
                  </div>
                  
                  <div class="form-group">
                    <label for="crawler-count">Max Items (1–50)</label>
                    <input type="number" id="crawler-count" value="50" min="1" max="50">
                  </div>
                  
                  <div class="mode-selection">
                    <div class="mode-option sd" onclick="selectCrawlerMode('sd')">
                      <input type="radio" name="crawlerMode" value="sd" id="crawler-mode-sd">
                      <label for="crawler-mode-sd">SD</label>
                      <span class="mode-desc">Structured Data + Patterns</span>
                    </div>
                    <div class="mode-option llm" onclick="selectCrawlerMode('llm')">
                      <input type="radio" name="crawlerMode" value="llm" id="crawler-mode-llm">
                      <label for="crawler-mode-llm">LLM</label>
                      <span class="mode-desc">AI Extraction Only</span>
                    </div>
                    <div class="mode-option auto active" onclick="selectCrawlerMode('auto')">
                      <input type="radio" name="crawlerMode" value="auto" id="crawler-mode-auto" checked>
                      <label for="crawler-mode-auto">AUTO</label>
                      <span class="mode-desc">Smart Fallback</span>
                    </div>
                  </div>
                  
                  <button class="btn" onclick="runCrawlerInline()">Run Crawler</button>
                  <div id="crawler-result" class="result" style="display:none;"></div>
                </div>
              </div>
            </div>
          </div>

          <script>
            function toggleSidebar() {
              const sidebar = document.querySelector('.sidebar');
              sidebar.classList.toggle('open');
              // Adjust main content margin when sidebar is toggled on desktop
              if (window.innerWidth > 768) {
                const mainContent = document.querySelector('.main-content');
                if (sidebar.classList.contains('open')) {
                  mainContent.style.marginLeft = '280px';
                } else {
                  mainContent.style.marginLeft = '0';
                }
              }
            }
            
            function showSection(sectionId, clickedElement) {
              // Hide all sections
              document.querySelectorAll('.content-section').forEach(section => {
                section.style.display = 'none';
              });
              
              // Remove active class from all nav items
              document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.remove('active');
              });
              
              // Show selected section
              document.getElementById(sectionId).style.display = 'block';
              
              // Add active class to clicked nav item
              if (clickedElement) {
                clickedElement.classList.add('active');
              }
              
              // Close sidebar on mobile after selection
              if (window.innerWidth <= 768) {
                document.querySelector('.sidebar').classList.remove('open');
              }
            }
            
            // Mode selection functions
            function selectMonitorMode(mode) {
              const sectionElement = document.getElementById('monitor');
              // Remove active class from all options
              sectionElement.querySelectorAll('.mode-option').forEach(opt => opt.classList.remove('active'));
              // Add active class to selected option
              const selectedOption = sectionElement.querySelector('[onclick*=\"selectMonitorMode(\'' + mode + '\')\"]');
              if (selectedOption) {
                selectedOption.classList.add('active');
                // Check the radio button
                sectionElement.querySelector('#monitor-mode-' + mode).checked = true;
              }
            }
            
            function selectExtractMode(mode) {
              const sectionElement = document.getElementById('extract');
              // Remove active class from all options
              sectionElement.querySelectorAll('.mode-option').forEach(opt => opt.classList.remove('active'));
              // Add active class to selected option
              const selectedOption = sectionElement.querySelector('[onclick*=\"selectExtractMode(\'' + mode + '\')\"]');
              if (selectedOption) {
                selectedOption.classList.add('active');
                // Check the radio button
                sectionElement.querySelector('#extract-mode-' + mode).checked = true;
              }
            }
            
            function selectCrawlerMode(mode) {
              const sectionElement = document.getElementById('crawler');
              // Remove active class from all options
              sectionElement.querySelectorAll('.mode-option').forEach(opt => opt.classList.remove('active'));
              // Add active class to selected option
              const selectedOption = sectionElement.querySelector('[onclick*=\"selectCrawlerMode(\'' + mode + '\')\"]');
              if (selectedOption) {
                selectedOption.classList.add('active');
                // Check the radio button
                sectionElement.querySelector('#crawler-mode-' + mode).checked = true;
              }
            }
            
            
            // API functions
            async function runMonitor() {
              const resultDiv = document.getElementById('monitor-result');
              resultDiv.style.display = 'block';
              resultDiv.textContent = 'Monitoring article list...';
              resultDiv.className = 'result loading';
              
              try {
                const selectedMode = document.querySelector('input[name=\"monitorMode\"]:checked').value;
                
                const response = await fetch('/monitor', {
                  method: 'POST', 
                  headers: { 'Content-Type': 'application/json' }, 
                  body: JSON.stringify({
                    url: document.getElementById('monitor-url').value,
                    mode: selectedMode
                  })
                });
                
                const result = await response.json();
                if (result.success) {
                  resultDiv.textContent = JSON.stringify(result, null, 2);
                  resultDiv.className = 'result success';
                } else {
                  resultDiv.textContent = 'Error: ' + result.error;
                  resultDiv.className = 'result error';
                }
              } catch (error) {
                resultDiv.textContent = 'Error: ' + error.message;
                resultDiv.className = 'result error';
              }
            }
            
            async function runExtract() {
              const resultDiv = document.getElementById('extract-result');
              resultDiv.style.display = 'block';
              resultDiv.textContent = 'Extracting article...';
              resultDiv.className = 'result loading';
              
              try {
                const selectedMode = document.querySelector('input[name=\"extractMode\"]:checked').value;
                
                const response = await fetch('/extract', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    url: document.getElementById('extract-url').value,
                    kind: document.getElementById('extract-kind').value,
                    llmMode: selectedMode
                  })
                });
                
                const result = await response.json();
                if (result.error) {
                  resultDiv.textContent = 'Error: ' + result.error;
                  resultDiv.className = 'result error';
                } else {
                  resultDiv.textContent = JSON.stringify(result, null, 2);
                  resultDiv.className = 'result success';
                }
              } catch (error) {
                resultDiv.textContent = 'Error: ' + error.message;
                resultDiv.className = 'result error';
              }
            }
            
            // Auto workflow removed
            
            async function runCrawlerInline() {
              const resultDiv = document.getElementById('crawler-result');
              resultDiv.style.display = 'block';
              resultDiv.textContent = 'Crawling...';
              resultDiv.className = 'result loading';
              try {
                const selectedMode = document.querySelector('input[name=\"crawlerMode\"]:checked').value;
                const response = await fetch('/crawl', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    url: document.getElementById('crawler-url').value,
                    count: parseInt(document.getElementById('crawler-count').value),
                    crawlMode: selectedMode
                  })
                });
                const res = await response.json();
                if (res.success) {
                  resultDiv.textContent = JSON.stringify(res, null, 2);
                  resultDiv.className = 'result success';
                } else {
                  resultDiv.textContent = 'Error: ' + res.error;
                  resultDiv.className = 'result error';
                }
              } catch (e) {
                resultDiv.textContent = 'Error: ' + e.message;
                resultDiv.className = 'result error';
              }
            }

            // Labs inline helpers
            async function runSmartScraper() {
              const resultEl = document.getElementById('smart-result');
              resultEl.style.display = 'block';
              resultEl.textContent = 'Running SmartScraper...';
              resultEl.className = 'result loading';
              try {
                const payload = { 
                  url: document.getElementById('smart-url').value, 
                  prompt: document.getElementById('smart-prompt').value 
                };
                const res = await fetch('/labs/smart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const json = await res.json();
                if (json.success) {
                  resultEl.textContent = JSON.stringify(json.data, null, 2);
                  resultEl.className = 'result success';
                } else {
                  resultEl.textContent = 'Error: ' + json.error;
                  resultEl.className = 'result error';
                }
              } catch (e) {
                resultEl.textContent = 'Error: ' + e.message;
                resultEl.className = 'result error';
              }
            }

            async function runSearchGraph() {
              const resultEl = document.getElementById('search-result');
              resultEl.style.display = 'block';
              resultEl.textContent = 'Running SearchGraph...';
              resultEl.className = 'result loading';
              try {
                const payload = { 
                  query: document.getElementById('search-query').value, 
                  count: parseInt(document.getElementById('search-count').value), 
                  prompt: document.getElementById('search-prompt').value 
                };
                const res = await fetch('/labs/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const json = await res.json();
                if (json.success) {
                  resultEl.textContent = JSON.stringify(json.data, null, 2);
                  resultEl.className = 'result success';
                } else {
                  resultEl.textContent = 'Error: ' + json.error;
                  resultEl.className = 'result error';
                }
              } catch (e) {
                resultEl.textContent = 'Error: ' + e.message;
                resultEl.className = 'result error';
              }
            }

            async function runMultiGraph() {
              const resultEl = document.getElementById('multi-result');
              resultEl.style.display = 'block';
              resultEl.textContent = 'Running MultiGraph...';
              resultEl.className = 'result loading';
              try {
                const payload = { 
                  urls: document.getElementById('multi-urls').value.split('\\n').filter(u => u.trim()), 
                  prompt: document.getElementById('multi-prompt').value 
                };
                const res = await fetch('/labs/multi', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const json = await res.json();
                if (json.success) {
                  resultEl.textContent = JSON.stringify(json.data, null, 2);
                  resultEl.className = 'result success';
                } else {
                  resultEl.textContent = 'Error: ' + json.error;
                  resultEl.className = 'result error';
                }
              } catch (e) {
                resultEl.textContent = 'Error: ' + e.message;
                resultEl.className = 'result error';
              }
            }
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
              transform: translateX(-100%);
              transition: transform 0.3s ease;
              z-index: 1000;
            }
            .sidebar.open { 
              transform: translateX(0); 
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

@app.get("/crawler", response_class=HTMLResponse)
def crawler():
    return (
        """
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
          <title>OmniScrape Crawler</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; margin: 32px; color: #222; }
            h1 { margin-bottom: 8px; }
            .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin-top: 16px; }
            .name { font-weight: 700; font-size: 16px; margin-bottom: 8px; }
            .desc { color: #555; margin-bottom: 12px; }
            .form { margin-top: 12px; }
            input, textarea, select { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 6px; margin-bottom: 8px; box-sizing: border-box; }
            button { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
            button:hover { background: #1d4ed8; }
            .result { margin-top: 12px; padding: 12px; background: #f9fafb; border-radius: 6px; white-space: pre-wrap; font-family: monospace; font-size: 12px; }
            .error { background: #fef2f2; color: #dc2626; }
            .loading { color: #6b7280; }
            a { color: #2563eb; text-decoration: none; }
            .note { background: #fef3c7; padding: 8px; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
            .mode-selection { display: flex; gap: 12px; margin: 16px 0; }
            .mode-option { 
              flex: 1; 
              border: 2px solid #e5e7eb; 
              border-radius: 8px; 
              padding: 12px; 
              cursor: pointer; 
              transition: all 0.2s;
              text-align: center;
            }
            .mode-option:hover { border-color: #4285f4; background: #f9fafb; }
            .mode-option.active { 
              border-color: #4285f4; 
              background: #eff6ff; 
            }
            .mode-option input[type=\"radio\"] { display: none; }
            .mode-option label { 
              display: block; 
              font-weight: 700; 
              font-size: 16px; 
              margin-bottom: 4px;
              cursor: pointer;
            }
            .mode-desc { 
              font-size: 12px; 
              color: #6b7280; 
              display: block;
            }
            .mode-option.active label { color: #4285f4; }
          </style>
        </head>
        <body>
          <h1>🕷️ Universal Article Crawler</h1>
          <p>Crawl article list pages and extract full content using cascading fallback strategy.</p>
          
          <div class=\"note\">
            <strong>How it works:</strong> 
            1. <strong>Structured Data</strong> - Fast extraction from JSON-LD, Microdata
            2. <strong>Pattern Matching</strong> - Common HTML patterns (article, li, etc.)
            3. <strong>AI Fallback</strong> - Universal extraction for any page structure
          </div>

          <div class=\"card\">
            <div class=\"name\">Article List Crawler</div>
            <div class=\"desc\">Provide any article list page URL and get the top N articles with full content.</div>
            
            <div class=\"mode-selection\">
              <div class=\"mode-option\" onclick=\"selectMode('sd')\">
                <input type=\"radio\" name=\"crawlMode\" value=\"sd\" id=\"mode-sd\">
                <label for=\"mode-sd\">SD</label>
                      <span class=\"mode-desc\">Structured Data + Pattern Recognition</span>
              </div>
              <div class=\"mode-option\" onclick=\"selectMode('llm')\">
                <input type=\"radio\" name=\"crawlMode\" value=\"llm\" id=\"mode-llm\">
                <label for=\"mode-llm\">LLM</label>
                      <span class=\"mode-desc\">AI-Powered Content Recognition</span>
              </div>
              <div class=\"mode-option active\" onclick=\"selectMode('auto')\">
                <input type=\"radio\" name=\"crawlMode\" value=\"auto\" id=\"mode-auto\" checked>
                <label for=\"mode-auto\">AUTO</label>
                <span class=\"mode-desc\">Smart Fallback</span>
              </div>
            </div>
            
            <div class=\"form\">
              <input type=\"text\" id=\"crawl-url\" placeholder=\"Enter article list URL\" value=\"https://column.etnetchina.cn/list/article-latest\">
              <input type=\"number\" id=\"crawl-count\" placeholder=\"Number of articles\" value=\"5\" min=\"1\" max=\"50\">
              <button onclick=\"runCrawler()\">🕷️ Crawl Articles</button>
              <div id=\"crawl-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <p style=\"margin-top:16px;\"><a href=\"/\">← Back</a></p>

          <script>
            
            async function runCrawler() {
              const resultDiv = document.getElementById('crawl-result');
              resultDiv.style.display = 'block';
              resultDiv.textContent = 'Crawling articles...';
              resultDiv.className = 'result loading';
              
              try {
                const selectedMode = document.querySelector('input[name=\"crawlMode\"]:checked').value;
                
                const response = await fetch('/crawl', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    url: document.getElementById('crawl-url').value,
                    count: parseInt(document.getElementById('crawl-count').value),
                    crawlMode: selectedMode
                  })
                });
                
                const result = await response.json();
                if (result.success) {
                  resultDiv.textContent = JSON.stringify(result, null, 2);
                  resultDiv.className = 'result';
                } else {
                  resultDiv.textContent = 'Error: ' + result.error;
                  resultDiv.className = 'result error';
                }
              } catch (error) {
                resultDiv.textContent = 'Error: ' + error.message;
                resultDiv.className = 'result error';
              }
            }
          </script>
        </body>
        </html>
        """
    )

@app.post("/crawl", tags=["extraction"], summary="Crawl Article List", description="Crawl article list page and extract full content for each article using cascading fallback strategy")
async def do_crawl(req: CrawlRequest, request: Request):
    try:
        # Check if client disconnected
        if await request.is_disconnected():
            return {"error": "Client disconnected"}
        
        # Validate count
        if req.count < 1 or req.count > 50:
            return {"error": "Count must be between 1 and 50"}
        
        # For now, return a test response due to OpenAI API region restrictions
        # TODO: Implement proper crawling once API issues are resolved
        
        return {
            "success": True,
            "url": str(req.url),
            "requested_count": req.count,
            "found_count": 2,
            "crawlMode": req.crawlMode,
            "articles": [
                {
                    "title": "Sample Crawled Article 1",
                    "url": "https://example.com/article1",
                    "content": "This is the full content of the first crawled article. The crawling functionality requires resolving OpenAI API region restrictions.",
                    "author": "Sample Author 1",
                    "published_date": "2024-01-01",
                    "crawled_at": datetime.now().isoformat()
                },
                {
                    "title": "Sample Crawled Article 2",
                    "url": "https://example.com/article2", 
                    "content": "This is the full content of the second crawled article. The crawling functionality requires resolving OpenAI API region restrictions.",
                    "author": "Sample Author 2",
                    "published_date": "2024-01-02",
                    "crawled_at": datetime.now().isoformat()
                }
            ],
            "crawled_at": datetime.now().isoformat(),
            "note": "This is a test response. Full crawling requires fixing OpenAI API region restrictions."
        }
        
    except asyncio.CancelledError:
        return {"error": "Request cancelled by client"}
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

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

@app.post("/monitor", tags=["extraction"], summary="Monitor Article List", description="Extract article list metadata without fetching full content")
async def monitor_articles(req: MonitorRequest, request: Request):
    try:
        if await request.is_disconnected():
            return {"error": "Client disconnected"}
        
        # For now, return a simple test response to verify the endpoint works
        # TODO: Implement proper article list extraction without ScrapeGraphAI dependency
        
        return {
            "success": True,
            "url": str(req.url),
            "mode": req.mode,
            "article_count": 3,
            "articles": [
                {
                    "title": "Test Article 1",
                    "url": "https://example.com/article1",
                    "published_date": "2024-01-01",
                    "author": "Test Author 1"
                },
                {
                    "title": "Test Article 2", 
                    "url": "https://example.com/article2",
                    "published_date": "2024-01-02",
                    "author": "Test Author 2"
                },
                {
                    "title": "Test Article 3",
                    "url": "https://example.com/article3", 
                    "published_date": "2024-01-03",
                    "author": "Test Author 3"
                }
            ],
            "monitored_at": datetime.now().isoformat(),
            "note": "This is a test response. Full implementation requires fixing OpenAI API region restrictions."
        }
    except asyncio.CancelledError:
        return {"error": "Request cancelled by client"}
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.post("/extract", tags=["extraction"], summary="Extract Article or Product", description="Extract structured data from articles or products using cascading fallback strategy")
async def do_extract(req: ExtractRequest, request: Request):
    try:
        # Check if client disconnected
        if await request.is_disconnected():
            return {"error": "Client disconnected"}
        
        # For now, return a test response due to OpenAI API region restrictions
        # TODO: Implement proper extraction once API issues are resolved
        
        return {
            "success": True,
            "url": str(req.url),
            "kind": req.kind,
            "mode": req.llmMode,
            "data": {
                "title": "Sample Article Title",
                "content": "This is sample content extracted from the article. The full extraction functionality requires resolving OpenAI API region restrictions.",
                "author": "Sample Author",
                "published_date": "2024-01-01",
                "extraction_method": "test_mode"
            },
            "extracted_at": datetime.now().isoformat(),
            "note": "This is a test response. Full extraction requires fixing OpenAI API region restrictions."
        }
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
