"""数据访问层：加载并对 现网数据.csv 做过滤/采样。粒度：一行=一个 session=一条 query。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

_COLS = ["cluster_id", "cluster_size", "top_category", "sub_intent", "query_text"]


class Dataset:
    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self.df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        self.df["cluster_size"] = pd.to_numeric(self.df["cluster_size"], errors="coerce").fillna(0).astype(int)

    def stats(self) -> dict[str, int]:
        return {
            "total_rows": int(len(self.df)),
            "n_clusters": int(self.df["cluster_id"].nunique()),
            "n_categories": int(self.df["top_category"].nunique()),
            "n_intents": int(self.df["sub_intent"].nunique()),
            "noise_rows": int((self.df["cluster_id"] == -1).sum()),
        }

    def top_categories(self, n: int) -> list[dict[str, Any]]:
        g = self.df.groupby("top_category").agg(rows=("query_text", "size"), clusters=("cluster_id", "nunique"))
        g = g.sort_values("rows", ascending=False).head(max(0, int(n)))
        return [{"top_category": idx, "rows": int(r.rows), "clusters": int(r.clusters)} for idx, r in g.iterrows()]

    def sub_intents(self, category: str | None = None) -> list[dict[str, Any]]:
        df = self.df if category is None else self.df[self.df["top_category"] == category]
        g = df.groupby(["top_category", "sub_intent"]).size().reset_index(name="rows")
        g = g.sort_values("rows", ascending=False)
        return [{"top_category": r.top_category, "sub_intent": r.sub_intent, "rows": int(r.rows)} for r in g.itertuples()]

    def filter(self, category=None, sub_intent=None, cluster_id=None, keyword=None, limit=None) -> list[dict[str, Any]]:
        df = self.df
        if category is not None:
            df = df[df["top_category"] == category]
        if sub_intent is not None:
            df = df[df["sub_intent"] == sub_intent]
        if cluster_id is not None:
            df = df[df["cluster_id"] == int(cluster_id)]
        if keyword:
            df = df[df["query_text"].str.contains(keyword, case=False, na=False, regex=False)]
        if limit is not None:
            df = df.head(max(0, int(limit)))
        return df[_COLS].to_dict(orient="records")

    def sample(self, n, strategy="random", category=None, sub_intent=None, top_k=None, per_category=None) -> list[dict[str, Any]]:
        df = self.df
        if category is not None:
            df = df[df["top_category"] == category]
        if sub_intent is not None:
            df = df[df["sub_intent"] == sub_intent]
        n = int(n)
        if strategy == "random":
            k = min(n, len(df))
            out = df.sample(n=k, random_state=42) if k > 0 else df.head(0)
            return out[_COLS].to_dict(orient="records")
        if strategy == "top_by_cluster_size":
            out = df.sort_values("cluster_size", ascending=False).head(n)
            return out[_COLS].to_dict(orient="records")
        if strategy == "stratified_by_category":
            if top_k is not None:
                keep = [c["top_category"] for c in self.top_categories(int(top_k))]
                df = df[df["top_category"].isin(keep)]
            if per_category is not None:
                per = int(per_category)
                parts = [g.sample(n=min(per, len(g)), random_state=42) for _, g in df.groupby("top_category")]
                out = pd.concat(parts) if parts else df.head(0)
            else:
                counts = df["top_category"].value_counts()
                total = int(counts.sum()) or 1
                parts = []
                for cat, cnt in counts.items():
                    take = max(1, round(n * cnt / total))
                    g = df[df["top_category"] == cat]
                    parts.append(g.sample(n=min(take, len(g)), random_state=42))
                out = pd.concat(parts) if parts else df.head(0)
                out = out.head(n)
            return out[_COLS].to_dict(orient="records")
        raise ValueError(f"unknown strategy: {strategy}")
