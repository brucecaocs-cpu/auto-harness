"""harness 数据 API 服务 —— 仅为 nanobot WebUI 的 /data 页面提供数据查询后端。"""
from __future__ import annotations

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import load_settings

_PAGE_SIZE = 50
_DATA_COLS = ["cluster_id", "cluster_size", "top_category", "sub_intent", "query_text"]


def create_app() -> FastAPI:
    settings = load_settings()
    raw_df = pd.read_csv(settings.csv_path, encoding="utf-8-sig")

    app = FastAPI(title="auto-harness Data API")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

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
        page = d.iloc[offset : offset + limit]
        return {
            "total": total,
            "start": offset + 1 if total > 0 else 0,
            "end": min(offset + limit, total),
            "rows": page[_DATA_COLS].fillna("").to_dict(orient="records"),
        }

    @app.get("/api/data/stats")
    async def data_stats():
        return {
            "total_rows": len(raw_df),
            "columns": list(_DATA_COLS),
            "n_categories": int(raw_df["top_category"].nunique()),
            "n_intents": int(raw_df["sub_intent"].nunique()),
            "n_clusters": int(raw_df["cluster_id"].nunique()),
        }

    @app.get("/api/data/categories")
    async def data_categories():
        g = raw_df.groupby("top_category").agg(rows=("query_text", "size"), clusters=("cluster_id", "nunique"))
        g = g.sort_values("rows", ascending=False)
        return [{"category": idx, "rows": int(r.rows), "clusters": int(r.clusters)} for idx, r in g.iterrows()]

    @app.get("/api/data/noise-ratio")
    async def data_noise_ratio():
        noise = int((raw_df["cluster_id"] == -1).sum())
        total = len(raw_df)
        return {"noise_rows": noise, "total_rows": total, "noise_pct": round(noise / total * 100, 1)}

    return app


def main() -> None:
    host, port = "127.0.0.1", 8766
    app = create_app()
    print(f"📋 auto-harness 数据 API → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
