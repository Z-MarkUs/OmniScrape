from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Literal
import orjson
import asyncio
from .pipeline import extract

class ExtractRequest(BaseModel):
    url: HttpUrl
    kind: Literal["article", "product"]
    llmMode: Literal["none", "llm", "auto"] = "auto"

app = FastAPI(
    title="OmniScrape API",
    description="Extract articles and products from any site via structured data, readability, and LLM fallbacks",
    version="0.1.0"
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
          </style>
        </head>
        <body>
          <h1>Labs</h1>
          <p>ScrapeGraphAI capabilities available for experimentation.</p>
          
          <div class=\"note\">
            <strong>Note:</strong> Some graphs require additional API keys (Bing Search API for SearchGraph). 
            OpenAI API key is required for all LLM-powered graphs.
          </div>

          <div class=\"card\">
            <div class=\"name\">SmartScraperGraph</div>
            <div class=\"desc\">Single-page scraper that only needs a user prompt and an input source.</div>
            <div class=\"form\">
              <input type=\"text\" id=\"smart-url\" placeholder=\"Enter URL\" value=\"https://example.com\">
              <textarea id=\"smart-prompt\" placeholder=\"Enter your extraction prompt\" rows=\"3\">Extract the main title, author, and key points from this article</textarea>
              <button onclick=\"runSmartScraper()\">Run SmartScraper</button>
              <div id=\"smart-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <div class=\"card\">
            <div class=\"name\">SearchGraph</div>
            <div class=\"desc\">Multi-page scraper that extracts information from the top n search results of a search engine.</div>
            <div class=\"form\">
              <input type=\"text\" id=\"search-query\" placeholder=\"Enter search query\" value=\"artificial intelligence news\">
              <input type=\"number\" id=\"search-count\" placeholder=\"Number of results\" value=\"3\" min=\"1\" max=\"10\">
              <textarea id=\"search-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Extract the title, summary, and publication date from each article</textarea>
              <button onclick=\"runSearchGraph()\">Run SearchGraph</button>
              <div id=\"search-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <div class=\"card\">
            <div class=\"name\">SpeechGraph</div>
            <div class=\"desc\">Single-page scraper that extracts information from a website and generates an audio file.</div>
            <div class=\"form\">
              <input type=\"text\" id=\"speech-url\" placeholder=\"Enter URL\" value=\"https://example.com\">
              <textarea id=\"speech-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Extract the main content and convert it to speech</textarea>
              <button onclick=\"runSpeechGraph()\">Run SpeechGraph</button>
              <div id=\"speech-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <div class=\"card\">
            <div class=\"name\">ScriptCreatorGraph</div>
            <div class=\"desc\">Single-page scraper that extracts information from a website and generates a Python script.</div>
            <div class=\"form\">
              <input type=\"text\" id=\"script-url\" placeholder=\"Enter URL\" value=\"https://example.com\">
              <textarea id=\"script-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Create a Python script to extract product information from this page</textarea>
              <button onclick=\"runScriptCreator()\">Run ScriptCreator</button>
              <div id=\"script-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <div class=\"card\">
            <div class=\"name\">SmartScraperMultiGraph</div>
            <div class=\"desc\">Multi-page scraper that extracts information from multiple pages given a single prompt and a list of sources.</div>
            <div class=\"form\">
              <textarea id=\"multi-urls\" placeholder=\"Enter URLs (one per line)\" rows=\"3\">https://example.com
https://httpbin.org/html
https://httpbin.org/json</textarea>
              <textarea id=\"multi-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Extract the title and main content from each page</textarea>
              <button onclick=\"runSmartScraperMulti()\">Run SmartScraperMulti</button>
              <div id=\"multi-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <div class=\"card\">
            <div class=\"name\">ScriptCreatorMultiGraph</div>
            <div class=\"desc\">Multi-page scraper that generates a Python script for extracting information from multiple pages and sources.</div>
            <div class=\"form\">
              <textarea id=\"script-multi-urls\" placeholder=\"Enter URLs (one per line)\" rows=\"3\">https://example.com
https://httpbin.org/html</textarea>
              <textarea id=\"script-multi-prompt\" placeholder=\"Enter extraction prompt\" rows=\"3\">Create a Python script to extract structured data from these pages</textarea>
              <button onclick=\"runScriptCreatorMulti()\">Run ScriptCreatorMulti</button>
              <div id=\"script-multi-result\" class=\"result\" style=\"display:none;\"></div>
            </div>
          </div>

          <p style=\"margin-top:16px;\"><a href=\"/\">← Back</a></p>

          <script>
            async function runGraph(graphType, data) {
              const resultDiv = document.getElementById(graphType + '-result');
              resultDiv.style.display = 'block';
              resultDiv.textContent = 'Loading...';
              resultDiv.className = 'result loading';
              
              try {
                const response = await fetch('/labs/' + graphType, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(data)
                });
                
                const result = await response.json();
                if (result.success) {
                  resultDiv.textContent = JSON.stringify(result.data, null, 2);
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
            
            function runSmartScraper() {
              runGraph('smart', {
                url: document.getElementById('smart-url').value,
                prompt: document.getElementById('smart-prompt').value
              });
            }
            
            function runSearchGraph() {
              runGraph('search', {
                query: document.getElementById('search-query').value,
                count: parseInt(document.getElementById('search-count').value),
                prompt: document.getElementById('search-prompt').value
              });
            }
            
            function runSpeechGraph() {
              runGraph('speech', {
                url: document.getElementById('speech-url').value,
                prompt: document.getElementById('speech-prompt').value
              });
            }
            
            function runScriptCreator() {
              runGraph('script', {
                url: document.getElementById('script-url').value,
                prompt: document.getElementById('script-prompt').value
              });
            }
            
            function runSmartScraperMulti() {
              runGraph('multi', {
                urls: document.getElementById('multi-urls').value.split('\\n').filter(u => u.trim()),
                prompt: document.getElementById('multi-prompt').value
              });
            }
            
            function runScriptCreatorMulti() {
              runGraph('script-multi', {
                urls: document.getElementById('script-multi-urls').value.split('\\n').filter(u => u.trim()),
                prompt: document.getElementById('script-multi-prompt').value
              });
            }
          </script>
        </body>
        </html>
        """
    )

# Labs API endpoints
@app.post("/labs/smart")
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

@app.post("/labs/search")
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

@app.post("/labs/speech")
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

@app.post("/labs/script")
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

@app.post("/labs/multi")
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

@app.post("/labs/script-multi")
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

@app.get("/health")
def health(): 
    return {"ok": True}

@app.post("/extract")
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
