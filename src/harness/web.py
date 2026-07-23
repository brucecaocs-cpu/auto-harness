"""harness Web 服务：聊天 Agent + 原始数据浏览，一个端口全服务。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .agent import AgentLoop
from .config import load_settings
from .data_tools import build_data_tools
from .dataset import Dataset
from .eval_tools import build_eval_tools
from .provider import OpenAICompatProvider
from .tools import ToolRegistry

_PAGE_SIZE = 50
_DATA_COLS = ["cluster_id", "cluster_size", "top_category", "sub_intent", "query_text"]
_NAV = '<div style="display:flex;gap:12px;font-size:13px"><a href="/" style="color:#a0d0ff">💬 对话</a><a href="/data" style="color:#a0d0ff">📋 数据查询</a></div>'

_CHAT_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>auto-harness</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f5f5;height:100vh;display:flex;flex-direction:column}
#header{background:#1a73e8;color:#fff;padding:12px 20px;font-size:16px;font-weight:600;display:flex;justify-content:space-between;align-items:center}
#chat{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:85%;padding:10px 14px;border-radius:8px;line-height:1.5;font-size:14px;white-space:pre-wrap}
.msg.user{background:#1a73e8;color:#fff;align-self:flex-end}
.msg.assistant{background:#fff;color:#222;align-self:flex-start;border:1px solid #e0e0e0}
.msg table{border-collapse:collapse;margin:6px 0;font-size:13px;width:100%}
.msg td,.msg th{border:1px solid #ccc;padding:4px 8px;text-align:left}
.msg th{background:#f0f0f0;font-weight:600}
.msg code{background:#f4f4f4;padding:1px 4px;border-radius:3px;font-size:13px}
.msg pre{background:#f8f8f8;padding:10px;border-radius:6px;overflow-x:auto;font-size:13px;margin:6px 0}
#input-area{display:flex;gap:8px;padding:12px 20px;background:#fff;border-top:1px solid #e0e0e0}
#input{flex:1;padding:10px 14px;border:1px solid #ddd;border-radius:6px;font-size:14px;outline:0}
#input:focus{border-color:#1a73e8}
#send{padding:10px 20px;background:#1a73e8;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer}
#send:disabled{opacity:.6}
#status{display:none;padding:8px 20px;color:#666;font-size:13px;border-top:1px solid #e0e0e0}
</style></head>
<body>
<div id="header"><span>auto-harness · 评测数据集 Agent</span>""" + _NAV + r"""</div>
<div id="chat"></div><div id="status">⏳ 处理中...</div>
<div id="input-area">
  <input id="input" placeholder="输入需求，如：帮我找出闹钟相关的100条现网query" autofocus>
  <button id="send" onclick="send()">发送</button>
</div>
<script>
let sid=localStorage.getItem("sid")||"";
if(!sid){sid=crypto.randomUUID();localStorage.setItem("sid",sid)}
const chat=document.getElementById("chat"),input=document.getElementById("input"),
  sendBtn=document.getElementById("send"),status=document.getElementById("status");
function esc(t){return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function md(t){
  t=t.replace(/^\|(.+)\|$/gm,(_,r)=>{const c=r.split("|").map(x=>`<td>${esc(x.trim())}</td>`).join("");if(/^[\s:-]+\s*$/.test(r.replace(/\|/g," ").trim()))return"";return`<tr>${c}</tr>`});
  t=t.replace(/(<tr>.*<\/tr>(\s*<tr>.*<\/tr>)*)/g,'<table>$1</table>');
  t=t.replace(/```(\w*)\n?([\s\S]*?)```/g,'<pre><code>$2</code></pre>');
  t=t.replace(/`([^`]+)`/g,'<code>$1</code>');
  t=t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');t=t.replace(/\n/g,'<br>');return t}
function add(role,text){
  const d=document.createElement("div");d.className="msg "+role;
  d.innerHTML=role==="assistant"?md(text):esc(text);chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
async function send(){
  const q=input.value.trim();if(!q)return;input.value="";sendBtn.disabled=true;status.style.display="block";add("user",q);
  try{const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:q,session_id:sid})});
    const d=await r.json();if(d.error)add("assistant","⚠️ 错误："+d.error);else add("assistant",d.answer||"(空)")}
  catch(e){add("assistant","⚠️ 网络错误："+e.message)}
  finally{sendBtn.disabled=false;status.style.display="none"}}
input.addEventListener("keydown",e=>{if(e.key==="Enter")send()});
</script></body></html>"""

_DATA_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>原始数据查询 · auto-harness</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f5f5;display:flex;flex-direction:column;height:100vh}
#header{background:#333;color:#fff;padding:10px 20px;font-size:14px;display:flex;justify-content:space-between;align-items:center}
#header b{font-size:16px}
#filters{background:#fff;padding:10px 14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid #ddd;font-size:13px}
#filters input{padding:6px 8px;border:1px solid #ccc;border-radius:4px;font-size:12px;outline:none;width:130px}
#filters input:focus{border-color:#1a73e8}
#filters label{color:#555;margin-right:2px;font-size:12px}
#filters button{padding:6px 14px;background:#1a73e8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px}
#stats{padding:6px 14px;font-size:12px;color:#666;background:#fafafa;border-bottom:1px solid #eee}
#table-wrap{flex:1;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
thead th{position:sticky;top:0;background:#444;color:#fff;padding:8px 6px;text-align:left;z-index:1}
tbody td{padding:6px;border-bottom:1px solid #eee;max-width:400px;word-break:break-all}
tbody tr:hover{background:#e8f0fe}
#pager{display:flex;gap:8px;align-items:center;padding:10px 14px;background:#fff;border-top:1px solid #ddd;font-size:13px}
#pager button{padding:6px 12px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff;font-size:12px}
#pager button:disabled{opacity:.4}
</style></head><body>
<div id="header"><b>📋 原始数据查询</b>""" + _NAV + r"""</div>
<div id="filters">
  <label>cluster_id</label><input id="f-cluster" placeholder="如 294">
  <label>top_category</label><input id="f-category" placeholder="如 闹钟">
  <label>sub_intent</label><input id="f-intent" placeholder="如 设置闹钟">
  <label>query_text</label><input id="f-keyword" placeholder="关键词" style="width:180px">
  <button onclick="search()">🔍 筛选</button><button onclick="resetFilters()" style="background:#888">重置</button>
</div>
<div id="stats">共 <b id="s-total">0</b> 条｜当前 <b id="s-range">0-0</b></div>
<div id="table-wrap"><table>
<thead><tr><th style="width:70px">cluster_id</th><th style="width:80px">cluster_size</th><th style="width:120px">top_category</th><th style="width:120px">sub_intent</th><th>query_text</th></tr></thead>
<tbody id="tbody"><tr><td colspan="5">加载中...</td></tr></tbody></table></div>
<div id="pager">
  <button onclick="goPage(0)" id="b-first">⏮ 首页</button>
  <button onclick="goPage(cur-1)" id="b-prev">◀ 上页</button>
  <span>第 <b id="p-cur">1</b> / <b id="p-total">1</b> 页</span>
  <button onclick="goPage(cur+1)" id="b-next">下页 ▶</button>
</div>
<script>
let cur=0,total=0;
async function load(){
  document.body.classList.add('loading');
  const p={offset:cur*50,limit:50,_t:Date.now()};
  ['cluster','category','intent','keyword'].forEach((k,i)=>{
    const v=document.querySelectorAll('#filters input')[i].value.trim();
    if(v)p[['cluster_id','top_category','sub_intent','keyword'][i]]=v;
  });
  const r=await fetch('/api/data/rows?'+new URLSearchParams(p)),d=await r.json();
  total=Math.ceil(d.total/50)||1;
  document.getElementById('s-total').textContent=d.total.toLocaleString();
  document.getElementById('s-range').textContent=d.start+'-'+d.end;
  document.getElementById('p-cur').textContent=cur+1;document.getElementById('p-total').textContent=total;
  document.getElementById('b-prev').disabled=cur<=0;document.getElementById('b-next').disabled=cur>=total-1;
  document.getElementById('tbody').innerHTML=d.rows.map(r=>`<tr><td>${esc(r.cluster_id)}</td><td>${esc(r.cluster_size)}</td><td>${esc(r.top_category)}</td><td>${esc(r.sub_intent)}</td><td>${esc(r.query_text)}</td></tr>`).join('');
  document.body.classList.remove('loading')}
function esc(v){return v==null?'':String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function search(){cur=0;load()}
function resetFilters(){document.querySelectorAll('#filters input').forEach(e=>e.value='');cur=0;load()}
function goPage(n){if(n>=0&&n<total){cur=n;load()}}
load();
</script></body></html>"""


def create_app() -> FastAPI:
    settings = load_settings()
    provider = OpenAICompatProvider(settings.base_url, settings.api_key, settings.model)
    ds = Dataset(settings.csv_path)
    raw_df = pd.read_csv(settings.csv_path, encoding="utf-8-sig")
    registry = ToolRegistry()
    for t in build_data_tools(ds, settings.output_dir, provider):
        registry.register(t)
    for t in build_eval_tools(provider):
        registry.register(t)

    loops: dict[str, AgentLoop] = {}

    async def get_loop(sid: str) -> AgentLoop:
        if sid not in loops:
            loops[sid] = AgentLoop(provider, registry, max_iterations=settings.max_iterations)
        return loops[sid]

    app = FastAPI(title="auto-harness")

    # --- 聊天页面 + API ---
    @app.get("/")
    async def index():
        return HTMLResponse(_CHAT_HTML)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "model": settings.model}

    @app.post("/api/chat")
    async def chat(body: dict):
        query = body.get("query", "").strip()
        if not query:
            return JSONResponse({"error": "query 不能为空"}, status_code=400)
        sid = body.get("session_id", "default")
        loop = await get_loop(sid)
        try:
            answer = await loop.run(query)
            return {"answer": answer, "session_id": sid}
        except Exception as e:
            return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)

    @app.post("/api/reset")
    async def reset(body: dict):
        sid = body.get("session_id", "default")
        if sid in loops:
            loops[sid].reset()
        return {"ok": True}

    # --- 数据查询页面 + API ---
    @app.get("/data")
    async def data_page():
        return HTMLResponse(_DATA_HTML)

    @app.get("/api/data/rows")
    async def data_rows(
        offset: int = Query(0, ge=0),
        limit: int = Query(_PAGE_SIZE, ge=1, le=500),
        cluster_id: str = Query(""),
        top_category: str = Query(""),
        sub_intent: str = Query(""),
        keyword: str = Query(""),
    ):
        d = raw_df
        if cluster_id:
            try:
                d = d[d["cluster_id"] == int(cluster_id)]
            except ValueError:
                pass
        if top_category:
            d = d[d["top_category"].str.contains(top_category, case=False, na=False, regex=False)]
        if sub_intent:
            d = d[d["sub_intent"].str.contains(sub_intent, case=False, na=False, regex=False)]
        if keyword:
            d = d[d["query_text"].str.contains(keyword, case=False, na=False, regex=False)]
        total = len(d)
        page = d.iloc[offset: offset + limit]
        return {
            "total": total,
            "start": offset + 1 if total > 0 else 0,
            "end": min(offset + limit, total),
            "rows": page[_DATA_COLS].fillna("").to_dict(orient="records"),
        }

    @app.get("/api/data/stats")
    async def data_stats():
        return {"total_rows": len(raw_df), "columns": list(_DATA_COLS),
                "n_categories": int(raw_df["top_category"].nunique()),
                "n_intents": int(raw_df["sub_intent"].nunique()),
                "n_clusters": int(raw_df["cluster_id"].nunique())}

    return app


def main() -> None:
    host, port = "127.0.0.1", 8766
    app = create_app()
    print(f"🌐 auto-harness → http://{host}:{port}  (💬 对话 / 📋 /data 数据查询)")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()