"""配置：从 .env / 环境变量读取。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    api_key: str
    csv_path: Path
    output_dir: Path
    max_iterations: int = 10


def load_settings() -> Settings:
    load_dotenv(_ROOT / ".env")
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未找到 LLM_API_KEY，请在 .env 或环境变量中设置。")
    return Settings(
        base_url=os.environ.get("LLM_BASE_URL", "http://1239mxgn96959.vicp.fun:4009"),
        model=os.environ.get("LLM_MODEL", "deepseek-v4-pro"),
        api_key=api_key,
        csv_path=Path(os.environ.get("HARNESS_CSV", str(_ROOT / "data" / "现网数据.csv"))),
        output_dir=Path(os.environ.get("HARNESS_OUTPUT_DIR", str(_ROOT / "data" / "output"))),
        max_iterations=int(os.environ.get("HARNESS_MAX_ITER", "10")),
    )
