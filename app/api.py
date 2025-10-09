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
            .name { font-weight: 700; font-size: 16px; }
            .desc { color: #555; margin-top: 6px; }
            a { color: #2563eb; text-decoration: none; }
          </style>
        </head>
        <body>
          <h1>Labs</h1>
          <p>ScrapeGraphAI capabilities available for experimentation (descriptions only for now).</p>

          <div class=\"card\">
            <div class=\"name\">SmartScraperGraph</div>
            <div class=\"desc\">Single-page scraper that only needs a user prompt and an input source.</div>
          </div>
          <div class=\"card\">
            <div class=\"name\">SearchGraph</div>
            <div class=\"desc\">Multi-page scraper that extracts information from the top n search results of a search engine.</div>
          </div>
          <div class=\"card\">
            <div class=\"name\">SpeechGraph</div>
            <div class=\"desc\">Single-page scraper that extracts information from a website and generates an audio file.</div>
          </div>
          <div class=\"card\">
            <div class=\"name\">ScriptCreatorGraph</div>
            <div class=\"desc\">Single-page scraper that extracts information from a website and generates a Python script.</div>
          </div>
          <div class=\"card\">
            <div class=\"name\">SmartScraperMultiGraph</div>
            <div class=\"desc\">Multi-page scraper that extracts information from multiple pages given a single prompt and a list of sources.</div>
          </div>
          <div class=\"card\">
            <div class=\"name\">ScriptCreatorMultiGraph</div>
            <div class=\"desc\">Multi-page scraper that generates a Python script for extracting information from multiple pages and sources.</div>
          </div>

          <p style=\"margin-top:16px;\"><a href=\"/\">← Back</a></p>
        </body>
        </html>
        """
    )

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
