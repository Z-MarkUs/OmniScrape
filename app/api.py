from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl
from typing import Literal
import orjson
from .pipeline import extract

class ExtractRequest(BaseModel):
    url: HttpUrl
    kind: Literal["article", "product"]

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
            input, select { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 8px; }
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
              <button type=\"submit\">Extract</button>
            </form>
            <pre id=\"out\" hidden></pre>
          </div>

          <script>
            const form = document.getElementById('form');
            const out = document.getElementById('out');
            form.addEventListener('submit', async (e) => {
              e.preventDefault();
              const payload = { url: form.url.value, kind: form.kind.value };
              out.hidden = false; out.textContent = 'Loading...';
              try {
                const res = await fetch('/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const json = await res.json();
                if (json._llm_notice) { alert(json._llm_notice); }
                out.textContent = JSON.stringify(json, null, 2);
              } catch (err) {
                out.textContent = String(err);
              }
            });
          </script>
        </body>
        </html>
        """
    )

@app.get("/health")
def health(): 
    return {"ok": True}

@app.post("/extract")
async def do_extract(req: ExtractRequest):
    data = await extract(str(req.url), req.kind)
    return data
