#!/usr/bin/env python3
"""Screenshot API — URL to PNG/PDF with dark mode, mobile viewport support."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import asyncio, os, io, hashlib, time

app = FastAPI(title="Screenshot API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In production, use a Playwright browser pool. For Railway, use pw-userdata or chromium.
CACHE = {}  # Simple in-memory cache, TTL 600s


@app.get("/api/screenshot")
async def screenshot(
    url: str = Query(..., description="URL to capture"),
    format: str = Query("png", regex="^(png|jpeg|pdf)$"),
    dark_mode: bool = Query(False),
    mobile: bool = Query(False),
    full_page: bool = Query(False),
    width: int = Query(1280, ge=320, le=3840),
    height: int = Query(900, ge=240, le=2160),
):
    cache_key = hashlib.md5(f"{url}|{format}|{dark_mode}|{mobile}|{full_page}|{width}|{height}".encode()).hexdigest()
    if cache_key in CACHE and time.time() - CACHE[cache_key]["ts"] < 600:
        item = CACHE[cache_key]
        return Response(content=item["data"], media_type=item["mime"])

    cmd = ["playwright", "screenshot", "--browser", "chromium", url]
    if dark_mode:
        cmd.append("--color-scheme=dark")
    if mobile:
        cmd.append("--device=iPhone 15")
    if full_page:
        cmd.append("--full-page")
    cmd.extend(["--viewport-size", f"{width},{height}"])

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

    if proc.returncode != 0:
        raise HTTPException(500, f"Capture failed: {stderr.decode()[:200]}")

    mime = {"png": "image/png", "jpeg": "image/jpeg", "pdf": "application/pdf"}[format]
    CACHE[cache_key] = {"data": stdout, "mime": mime, "ts": time.time()}
    return Response(content=stdout, media_type=mime)


@app.get("/api/health")
def health():
    return {"status": "ok", "cached": len(CACHE)}


# Landing page
@app.get("/")
def landing():
    from fastapi.responses import HTMLResponse
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Screenshot API</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;min-height:100vh}
.hero{text-align:center;padding:80px 20px 60px}.hero h1{font-size:2.5rem;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px}
.hero p{font-size:1.1rem;color:#94a3b8;max-width:600px;margin:0 auto 32px}
.demo{max-width:800px;margin:0 auto;padding:20px}.demo input{width:100%;padding:14px;border-radius:8px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;font-size:1rem;margin-bottom:12px}
.demo input:focus{border-color:#38bdf8;outline:none}
.row{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.row label{display:flex;align-items:center;gap:6px;color:#94a3b8;font-size:.9rem;cursor:pointer}
.btn{padding:14px 32px;background:linear-gradient(135deg,#38bdf8,#818cf8);color:#fff;border:none;border-radius:8px;font-weight:600;font-size:1rem;cursor:pointer;width:100%}
.btn:hover{opacity:.9}
#result{margin-top:24px;text-align:center}#result img{max-width:100%;border-radius:8px;border:1px solid #334155}
code{display:block;background:#0f172a;padding:16px;border-radius:8px;margin:12px 0;font-size:.9rem;color:#38bdf8;word-break:break-all}
.pricing{max-width:800px;margin:60px auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;padding:20px}
.plan{background:#1e293b;border-radius:12px;padding:28px;text-align:center;border:1px solid #334155}
.plan h3{color:#38bdf8;margin-bottom:8px}.plan .price{font-size:2rem;font-weight:700;margin:12px 0}.plan .price span{font-size:1rem;color:#94a3b8}
</style></head><body>
<div class="hero"><h1>Screenshot API</h1><p>Convert any URL to PNG, JPEG or PDF. Dark mode, mobile viewport, full-page capture.</p></div>
<div class="demo"><input id="url" placeholder="https://example.com" value="https://github.com">
<div class="row">
<label><input type="checkbox" id="dark"> Dark Mode</label>
<label><input type="checkbox" id="mobile"> Mobile</label>
<label><input type="checkbox" id="full"> Full Page</label>
</div>
<button class="btn" onclick="capture()">Capture Screenshot</button>
<div id="result"></div>
<code>GET /api/screenshot?url=https://example.com&format=png&dark_mode=true</code>
</div>
<div class="pricing"><div class="plan"><h3>Free</h3><div class="price">$0<span>/mo</span></div><p>100 captures/day</p></div>
<div class="plan"><h3>Pro</h3><div class="price">$9<span>/mo</span></div><p>10,000 captures/day</p></div>
<div class="plan"><h3>Enterprise</h3><div class="price">$49<span>/mo</span></div><p>Unlimited captures</p></div></div>
<script>
async function capture(){var url=document.getElementById('url').value;var params=new URLSearchParams({url,format:'png'});
if(document.getElementById('dark').checked)params.set('dark_mode','true');
if(document.getElementById('mobile').checked)params.set('mobile','true');
if(document.getElementById('full').checked)params.set('full_page','true');
document.getElementById('result').innerHTML='<p style=color:#94a3b8>Capturing...</p>';
var r=await fetch('/api/screenshot?'+params);if(r.ok){var blob=await r.blob();
document.getElementById('result').innerHTML='<img src='+URL.createObjectURL(blob)+'>';}
else{document.getElementById('result').innerHTML='<p style=color:red>Error: '+(await r.json()).detail+'</p>';}}
</script></body></html>""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
