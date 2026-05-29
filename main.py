#!/usr/bin/env python3
"""Screenshot API — URL to PNG with dark mode, mobile viewport."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os, time, hashlib

app = FastAPI(title="Screenshot API", version="1.0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CACHE = {}

@app.get("/api/screenshot")
async def screenshot(
    url: str = Query(...), format: str = Query("png"), dark_mode: bool = Query(False),
    mobile: bool = Query(False), full_page: bool = Query(False),
    width: int = Query(1280, ge=320, le=3840), height: int = Query(900, ge=240, le=2160),
):
    cache_key = hashlib.md5(f"{url}|{format}|{dark_mode}|{mobile}|{full_page}|{width}|{height}".encode()).hexdigest()
    if cache_key in CACHE and time.time() - CACHE[cache_key]["ts"] < 600:
        item = CACHE[cache_key]
        return Response(content=item["data"], media_type=item["mime"])

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            ctx_kwargs = {"viewport": {"width": width, "height": height}}
            if dark_mode:
                ctx_kwargs["color_scheme"] = "dark"
            if mobile:
                ctx_kwargs["user_agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
                ctx_kwargs["viewport"] = {"width": 390, "height": 844}
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=20)
            data = await page.screenshot(full_page=full_page)
            await browser.close()
            CACHE[cache_key] = {"data": data, "mime": "image/png", "ts": time.time()}
            return Response(content=data, media_type="image/png")
    except ImportError:
        raise HTTPException(503, "Playwright not installed on this server. Add playwright to requirements.")
    except Exception as e:
        raise HTTPException(500, str(e)[:200])


@app.get("/api/health")
def health():
    return {"status": "ok", "cached": len(CACHE)}


@app.get("/")
def landing():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Screenshot API</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;min-height:100vh}
.hero{text-align:center;padding:60px 20px 40px}.hero h1{font-size:2.2rem;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}
.hero p{color:#94a3b8;max-width:500px;margin:0 auto 24px}
.demo{max-width:700px;margin:0 auto;padding:20px}
.demo input{width:100%;padding:12px;border-radius:8px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;font-size:.95rem;margin-bottom:10px}
.demo input:focus{border-color:#38bdf8;outline:none}
.row{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.row label{display:flex;align-items:center;gap:6px;color:#94a3b8;font-size:.9rem;cursor:pointer}
.btn{width:100%;padding:14px;background:linear-gradient(135deg,#38bdf8,#818cf8);border:none;border-radius:8px;color:#fff;font-weight:600;font-size:1rem;cursor:pointer}.btn:hover{opacity:.9}
#result{margin-top:20px;text-align:center}#result img{max-width:100%;border-radius:8px;border:1px solid #334155}
code{display:block;background:#0f172a;padding:14px;border-radius:8px;margin:12px 0;font-size:.85rem;color:#38bdf8;word-break:break-all;overflow-x:auto}
.pricing{max-width:700px;margin:60px auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;padding:20px}
.plan{background:#1e293b;border-radius:12px;padding:24px;text-align:center;border:1px solid #334155}
.plan h3{color:#38bdf8}.plan .price{font-size:1.8rem;font-weight:700;margin:10px 0}.plan .price span{font-size:.9rem;color:#94a3b8}
</style></head><body>
<div class="hero"><h1>Screenshot API</h1><p>Convert any URL to PNG. Dark mode, mobile viewport, full-page capture.</p></div>
<div class="demo"><input id="url" placeholder="https://example.com" value="https://github.com">
<div class="row"><label><input type="checkbox" id="dark"> Dark Mode</label><label><input type="checkbox" id="mobile"> Mobile</label><label><input type="checkbox" id="full"> Full Page</label></div>
<button class="btn" onclick="capture()">Capture Screenshot</button>
<div id="result"></div>
<code>GET /api/screenshot?url=https://github.com&dark_mode=true</code></div>
<div class="pricing"><div class="plan"><h3>Free</h3><div class="price">$0<span>/mo</span></div><p>100 captures/day</p></div>
<div class="plan"><h3>Pro</h3><div class="price">$9<span>/mo</span></div><p>10,000 captures/day</p></div></div>
<script>
async function capture(){var url=document.getElementById('url').value;var p=new URLSearchParams({url,format:'png'});
if(document.getElementById('dark').checked)p.set('dark_mode','true');if(document.getElementById('mobile').checked)p.set('mobile','true');
if(document.getElementById('full').checked)p.set('full_page','true');document.getElementById('result').innerHTML='<p style=color:#94a3b8>Capturing...</p>';
var r=await fetch('/api/screenshot?'+p);if(r.ok){var blob=await r.blob();document.getElementById('result').innerHTML='<img src='+URL.createObjectURL(blob)+'>';}
else{document.getElementById('result').innerHTML='<p style=color:red>'+((await r.json()).detail||'Error')+'</p>';}}
</script></body></html>""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
