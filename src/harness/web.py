"""harness Web 服务：极简聊天界面，无构建步骤。"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from .agent import AgentLoop
from .config import load_settings
from .data_tools import build_data_tools
from .dataset import Dataset
from .eval_tools import build_eval_tools
from .provider import OpenAICompatProvider
from .tools import ToolRegistry

_ROLES = ("assistant", "user")

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>auto-harness</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f5f5;height:100vh;display:flex;flex-direction:column}
#header{background:#1a73e8;color:#fff;padding:12px 20px;font-size:16px;font-weight:600}
#chat{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:85%;padding:10px 14px;border-radius:8px;line-height:1.5;font-size:14px;white-space:pre-wrap}
.msg.user{background:#1a73e8;color:#fff;align-self:flex-end}
.msg.assistant{background:#fff;color:#222;align-self:flex-start;border:1px solid #e0e0e0}
.msg table{border-collapse:collapse;margin:6px 0;font-size:13px;width:100%}
.msg td,.msg th{border:1px solid #ccc;padding:4px 8px;text-align:left}
.msg th{background:#f0f0f0;font-weight:600}
.msg code{background:#f4f4f4;padding:1px 4px;border-radius:3px;font-size:13px}
.msg pre{background:#f8f8f8;padding:10px;border-radius:6px;overflow-x:auto;font-size:13px;margin:6px 0}
.msg .csv-path{color:#1a73e8;text-decoration:underline;cursor:pointer;word-break:break-all}
#input-area{display:flex;gap:8px;padding:12px 20px;background:#fff;border-top:1px solid #e0e0e0}
#input{flex:1;padding:10px 14px;border:1px solid #ddd;border-radius:6px;font-size:14px;outline:0}
#input:focus{border-color:#1a73e8}
#send{padding:10px 20px;background:#1a73e8;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer}
#send:disabled{opacity:.6}
#status{display:none;padding:8px 20px;color:#666;font-size:13px;border-top:1px solid #e0e0e0}
.error{color:#d93025}
</style>
</head>
<body>
<div id="header">auto-harness · 评测数据集 Agent</div>
<div id="chat"></div>
<div id="status">⏳ 处理中...</div>
<div id="input-area">
  <input id="input" placeholder="输入需求，如：帮我找出闹钟相关的100条现网query" autofocus>
  <button id="send" onclick="send()">发送</button>
</div>
<script>
let sid = localStorage.getItem("sid") || "";
if(!sid) { sid = crypto.randomUUID(); localStorage.setItem("sid", sid); }
const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const status = document.getElementById("status");

function escapeHtml(t){return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function renderMarkdown(text){
  // tables: | a | b |
  text = text.replace(/^\|(.+)\|$/gm, (m,row) => {
    const cells = row.split("|").map(c => `<td>${escapeHtml(c.trim())}</td>`).join("");
    // detect header separator row
    if(/^[\s:-]+\s*$/.test(row.replace(/\|/g," ").trim())) return "";
    return `<tr>${cells}</tr>`;
  });
  text = text.replace(/(<tr>.*<\/tr>(\s*<tr>.*<\/tr>)*)/g, '<table>$1</table>');
  // code blocks
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  // inline code
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // bold
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // line breaks
  text = text.replace(/\n/g, '<br>');
  return text;
}
function addMsg(role, text){
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = role === "assistant" ? renderMarkdown(text) : escapeHtml(text);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}
async function send(){
  const q = input.value.trim();
  if(!q) return;
  input.value = ""; sendBtn.disabled = true; status.style.display = "block";
  addMsg("user", q);
  try{
    const r = await fetch("/api/chat", {method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({query:q, session_id:sid})});
    const data = await r.json();
    if(data.error) addMsg("assistant", "⚠️ 错误：" + data.error);
    else addMsg("assistant", data.answer || "(空)");
  }catch(e){
    addMsg("assistant", "⚠️ 网络错误：" + e.message);
  }finally{
    sendBtn.disabled = false; status.style.display = "none";
  }
}
input.addEventListener("keydown", e => { if(e.key === "Enter") send(); });
</script>
</body>
</html>"""


def create_app() -> FastAPI:
    settings = load_settings()
    provider = OpenAICompatProvider(settings.base_url, settings.api_key, settings.model)
    ds = Dataset(settings.csv_path)
    registry = ToolRegistry()
    for t in build_data_tools(ds, settings.output_dir):
        registry.register(t)
    for t in build_eval_tools(provider):
        registry.register(t)

    loops: dict[str, AgentLoop] = {}

    async def get_loop(sid: str) -> AgentLoop:
        if sid not in loops:
            loops[sid] = AgentLoop(provider, registry, max_iterations=settings.max_iterations)
        return loops[sid]

    app = FastAPI(title="auto-harness")

    @app.get("/")
    async def index():
        return HTMLResponse(_HTML)

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

    return app


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    app = create_app()
    print(f"🌐 auto-harness Web 服务 → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()