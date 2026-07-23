"""现网数据查看器 —— 可筛选、关键字搜索、翻页的 CSV 浏览器。

运行：python -m harness.data_viewer   →   http://127.0.0.1:8766
"""
from __future__ import annotations

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

from .config import load_settings

PAGE_SIZE = 50

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>原始数据查询 · auto-harness</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f5f5;display:flex;flex-direction:column;height:100vh}
#header{background:#333;color:#fff;padding:10px 20px;font-size:14px;display:flex;align-items:center;gap:16px}
#header b{font-size:16px}
#filters{background:#fff;padding:10px 14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid #ddd;font-size:13px}
#filters input,#filters select{padding:6px 8px;border:1px solid #ccc;border-radius:4px;font-size:12px;outline:none;width:130px}
#filters input:focus,#filters select:focus{border-color:#1a73e8}
#filters label{color:#555;margin-right:2px;font-size:12px}
#filters button{padding:6px 14px;background:#1a73e8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px}
#filters button:hover{background:#1557b0}
#stats{padding:6px 14px;font-size:12px;color:#666;background:#fafafa;border-bottom:1px solid #eee}
#table-wrap{flex:1;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
thead th{position:sticky;top:0;background:#444;color:#fff;padding:8px 6px;text-align:left;z-index:1}
tbody td{padding:6px;border-bottom:1px solid #eee;max-width:400px;word-break:break-all}
tbody tr:hover{background:#e8f0fe}
#pager{display:flex;gap:8px;align-items:center;padding:10px 14px;background:#fff;border-top:1px solid #ddd;font-size:13px}
#pager button{padding:6px 12px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff;font-size:12px}
#pager button:disabled{opacity:.4}
#pager span{color:#555}
.loading{opacity:.5}
</style>
</head>
<body>
<div id="header"><b>📋 原始数据查询</b><span id="header-stats"></span></div>
<div id="filters">
  <label>cluster_id</label><input id="f-cluster" placeholder="如 294">
  <label>top_category</label><input id="f-category" placeholder="如 闹钟">
  <label>sub_intent</label><input id="f-intent" placeholder="如 设置闹钟">
  <label>query_text</label><input id="f-keyword" placeholder="关键词" style="width:180px">
  <button onclick="search()">🔍 筛选</button>
  <button onclick="resetFilters()" style="background:#888">重置</button>
</div>
<div id="stats">共 <b id="s-total">0</b> 条｜当前 <b id="s-range">0-0</b></div>
<div id="table-wrap"><table>
<thead><tr><th style="width:70px">cluster_id</th><th style="width:80px">cluster_size</th><th style="width:120px">top_category</th><th style="width:120px">sub_intent</th><th>query_text</th></tr></thead>
<tbody id="tbody"><tr><td colspan="5">加载中...</td></tr></tbody>
</table></div>
<div id="pager">
  <button onclick="goPage(0)" id="b-first">⏮ 首页</button>
  <button onclick="goPage(cur-1)" id="b-prev">◀ 上页</button>
  <span>第 <b id="p-cur">1</b> / <b id="p-total">1</b> 页</span>
  <button onclick="goPage(cur+1)" id="b-next">下页 ▶</button>
  <span style="margin-left:12px">每页 <b>50</b> 条</span>
</div>
<script>
let cur=0,total=0,totalRows=0;
async function load(){
  document.body.classList.add('loading');
  const p={offset:cur*50,limit:50,_t:Date.now()};
  ['cluster','category','intent','keyword'].forEach((k,i)=>{
    const v=document.querySelectorAll('#filters input')[i].value.trim();
    if(v) p[['cluster_id','top_category','sub_intent','keyword'][i]]=v;
  });
  const r=await fetch('/api/data/rows?'+new URLSearchParams(p));
  const d=await r.json();
  totalRows=d.total; total=Math.ceil(totalRows/50)||1;
  document.getElementById('s-total').textContent=totalRows.toLocaleString();
  document.getElementById('s-range').textContent=`${d.start}-${d.end}`;
  document.getElementById('p-cur').textContent=cur+1;
  document.getElementById('p-total').textContent=total;
  document.getElementById('b-prev').disabled=cur<=0;
  document.getElementById('b-next').disabled=cur>=total-1;
  const tb=document.getElementById('tbody');
  tb.innerHTML=d.rows.map(r=>`<tr><td>${esc(r.cluster_id)}</td><td>${esc(r.cluster_size)}</td><td>${esc(r.top_category)}</td><td>${esc(r.sub_intent)}</td><td>${esc(r.query_text)}</td></tr>`).join('');
  document.body.classList.remove('loading');
}
function esc(v){return v==null?'':String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function search(){cur=0;load()}
function resetFilters(){document.querySelectorAll('#filters input').forEach(e=>e.value='');cur=0;load()}
function goPage(n){if(n>=0&&n<total){cur=n;load()}}
load();
</script>
</body>
</html>"""


def create_app() -> FastAPI:
    settings = load_settings()
    df = pd.read_csv(settings.csv_path, encoding="utf-8-sig")
    cols = ["cluster_id", "cluster_size", "top_category", "sub_intent", "query_text"]

    app = FastAPI(title="auto-harness Data Viewer")

    @app.get("/")
    @app.get("/data")
    async def data_page():
        return HTMLResponse(_HTML)

    @app.get("/api/data/rows")
    async def data_rows(
        offset: int = Query(0, ge=0),
        limit: int = Query(PAGE_SIZE, ge=1, le=500),
        cluster_id: str = Query(""),
        top_category: str = Query(""),
        sub_intent: str = Query(""),
        keyword: str = Query(""),
    ):
        d = df
        if cluster_id:
            try:
                cid = int(cluster_id)
                d = d[d["cluster_id"] == cid]
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
            "rows": page[cols].fillna("").to_dict(orient="records"),
        }

    @app.get("/api/data/stats")
    async def data_stats():
        return {
            "total_rows": len(df),
            "columns": list(cols),
            "n_categories": int(df["top_category"].nunique()),
            "n_intents": int(df["sub_intent"].nunique()),
            "n_clusters": int(df["cluster_id"].nunique()),
        }

    return app


def main() -> None:
    host = "127.0.0.1"
    port = 8766
    app = create_app()
    print(f"📋 auto-harness 原始数据查询 → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
