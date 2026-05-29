#!/usr/bin/env python3
"""Screenshot API v2 — URL status, metadata, SSL check. No browser needed."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, time, hashlib, socket, ssl, re
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlparse

app = FastAPI(title="Screenshot API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE = {}

@app.get("/api/check")
async def check_url(
    url: str = Query(..., description="URL to analyze"),
    format: str = Query("json", pattern="^(json|html|text)$"),
):
    cache_key = f"{url}|{format}"
    if cache_key in CACHE and time.time() - CACHE[cache_key]["ts"] < 300:
        return CACHE[cache_key]["data"]

    result = {"url": url, "timestamp": datetime.now().isoformat(), "status": None,
              "response_ms": None, "ssl_days": None, "headers": {}, "content_length": 0}

    start = time.time()
    try:
        req = Request(url, headers={"User-Agent": "ScreenshotAPI/2.0", "Accept": "text/html"})
        resp = urlopen(req, timeout=15)
        result["status"] = resp.status
        result["response_ms"] = round((time.time() - start) * 1000, 1)
        result["headers"] = dict(resp.headers)
        ct = resp.headers.get("Content-Type", "")
        content = resp.read(10000).decode("utf-8", errors="replace")
        result["content_length"] = int(resp.headers.get("Content-Length", 0))
        result["title"] = re.search(r"<title>(.+?)</title>", content, re.I)?.group(1) or ""
        result["meta_desc"] = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', content, re.I)?.group(1) or ""
    except URLError as e:
        result["error"] = str(e.reason)[:200] if e.reason else str(e)[:200]
    except Exception as e:
        result["error"] = str(e)[:200]

    # SSL check
    if url.startswith("https://"):
        try:
            host = urlparse(url).hostname
            ctx = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                    result["ssl_days"] = (not_after - datetime.now()).days
                    result["ssl_issuer"] = dict(cert.get("issuer", []))
                    result["ssl_valid_from"] = cert.get("notBefore", "")
                    result["ssl_valid_to"] = cert.get("notAfter", "")
        except Exception:
            pass

    CACHE[cache_key] = {"data": result, "ts": time.time()}

    if format == "html":
        import json
        return HTMLResponse(f"<pre>{json.dumps(result, indent=2)}</pre>")
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0", "cached": len(CACHE), "timestamp": datetime.now().isoformat()}


@app.get("/")
def landing():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>URL Check API</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;min-height:100vh}
.hero{text-align:center;padding:60px 20px 40px}.hero h1{font-size:2.2rem;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}
.hero p{color:#94a3b8;max-width:500px;margin:0 auto 24px}
.demo{max-width:700px;margin:0 auto;padding:20px}
.demo input{width:100%;padding:12px;border-radius:8px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;font-size:.95rem;margin-bottom:10px}
.demo input:focus{border-color:#38bdf8;outline:none}
.btn{width:100%;padding:14px;background:linear-gradient(135deg,#38bdf8,#818cf8);border:none;border-radius:8px;color:#fff;font-weight:600;font-size:1rem;cursor:pointer}.btn:hover{opacity:.9}
#result{margin-top:20px;background:#1e293b;border-radius:8px;padding:16px;font-family:monospace;font-size:.85rem;white-space:pre-wrap;max-height:400px;overflow-y:auto;display:none;border:1px solid #334155}
.status-ok{color:#6ee7b7}.status-err{color:#fca5a5}.status-warn{color:#fde047}
code{display:block;background:#0f172a;padding:14px;border-radius:8px;margin:12px 0;font-size:.85rem;color:#38bdf8;word-break:break-all}
.pricing{max-width:700px;margin:60px auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;padding:20px}
.plan{background:#1e293b;border-radius:12px;padding:24px;text-align:center;border:1px solid #334155}
.plan h3{color:#38bdf8}.plan .price{font-size:1.8rem;font-weight:700;margin:10px 0}.plan .price span{font-size:.9rem;color:#94a3b8}
.spinner{display:inline-block;width:20px;height:20px;border:2px solid #334155;border-top:2px solid #38bdf8;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body>
<div class="hero"><h1>URL Check API</h1><p>Instant URL analysis: status codes, SSL certs, response times, metadata extraction. No browser needed.</p></div>
<div class="demo"><input id="url" placeholder="https://example.com" value="https://github.com">
<button class="btn" onclick="check()">Analyze URL</button>
<div id="result"></div>
<code>GET /api/check?url=https://github.com&format=json</code></div>
<div class="pricing"><div class="plan"><h3>Free</h3><div class="price">$0<span>/mo</span></div><p>500 checks/day</p></div>
<div class="plan"><h3>Pro</h3><div class="price">$9<span>/mo</span></div><p>50,000 checks/day</p></div></div>
<script>
async function check(){var url=document.getElementById('url').value;var rdiv=document.getElementById('result');rdiv.style.display='block';rdiv.textContent='Analyzing...';
var r=await fetch('/api/check?url='+encodeURIComponent(url));var d=await r.json();
var s=d.status?(d.status<400?'status-ok':'status-err'):'status-warn';
rdiv.innerHTML='Status: <span class='+s+'>'+(d.status||d.error||'?')+'</span> ('+(d.response_ms||'?')+'ms)\\nSSL Days: '+(d.ssl_days!=null?d.ssl_days+'':'?')+'\\nTitle: '+(d.title||'?')+'\\nDescription: '+(d.meta_desc||'?')+'\\nContent-Type: '+(d.headers['Content-Type']||'?');}
</script></body></html>""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
