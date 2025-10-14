from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from datetime import datetime
import os
import psutil


router = APIRouter()


@router.get("/health.json")
def health():
    status = "healthy"
    checks = {}

    openai_key = os.getenv("OPENAI_API_KEY")
    checks["openai_api"] = {
        "configured": bool(openai_key),
    }

    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()._asdict()
        disk = psutil.disk_usage("/")._asdict()
        checks["system"] = {"cpu_percent": cpu, "memory": mem, "disk": disk}
    except Exception:
        checks["system"] = {"error": "psutil unavailable"}

    return {
        "status": status,
        "time": datetime.now().isoformat(),
        "checks": checks,
    }


@router.get("/status")
def status_page():
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset=\"utf-8\" />
          <title>OmniScrape Status</title>
          <style>
            body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0}
            .wrap{max-width:900px;margin:40px auto;padding:0 16px}
            .card{background:#0b1220;border:1px solid #192038;border-radius:12px;padding:20px;margin-bottom:16px}
            h1{font-size:24px;margin:0 0 8px}
            .ok{color:#22c55e}
            .warn{color:#f59e0b}
            .bad{color:#ef4444}
            .row{display:flex;justify-content:space-between;align-items:center}
            .rss{font-size:13px;color:#93a4b7}
            .feed{white-space:pre-wrap;font-family:Menlo,Monaco,Consolas,monospace;font-size:12px;color:#cbd5e1}
          </style>
          <script>
            async function loadStatus(){
              const res = await fetch('/health.json');
              const data = await res.json();
              const el = document.getElementById('local-status');
              el.textContent = data.status === 'healthy' ? 'All systems operational' : 'Degraded';
              el.className = data.status === 'healthy' ? 'ok' : 'warn';
            }
            async function loadOpenAI(){
              try{
                const res = await fetch('/status/openai');
                const txt = await res.text();
                document.getElementById('openai-feed').textContent = txt;
              }catch(e){
                document.getElementById('openai-feed').textContent = 'Unable to load OpenAI status.';
              }
            }
            window.onload = ()=>{loadStatus();loadOpenAI();}
          </script>
        </head>
        <body>
          <div class=\"wrap\">
            <div class=\"card\">
              <div class=\"row\">
                <h1>OmniScrape Status</h1>
                <div id=\"local-status\" class=\"ok\">Loading…</div>
              </div>
              <div class=\"rss\">This page summarizes local checks and OpenAI platform status.</div>
            </div>
            <div class=\"card\">
              <div class=\"row\"><h1>OpenAI Platform</h1><div class=\"rss\">Source: status.openai.com RSS</div></div>
              <pre id=\"openai-feed\" class=\"feed\">Loading OpenAI status…</pre>
            </div>
          </div>
        </body>
        </html>
        """
    )


@router.get("/status/openai")
def status_openai():
    try:
        import urllib.request
        import xml.etree.ElementTree as ET
        rss_url = "https://status.openai.com/feed.rss"
        with urllib.request.urlopen(rss_url, timeout=5) as r:
            content = r.read()
        root = ET.fromstring(content)
        items = []
        for item in root.findall('.//item')[:3]:
            title = (item.findtext('title') or '').strip()
            pub = (item.findtext('pubDate') or '').strip()
            items.append(f"- {title}  ({pub})")
        return HTMLResponse("\n".join(items) if items else "No recent incidents.")
    except Exception as e:
        return HTMLResponse(f"Error loading RSS: {e}")



