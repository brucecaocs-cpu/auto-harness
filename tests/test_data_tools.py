import json
import os

import pytest

from harness.data_tools import build_data_tools
from harness.dataset import Dataset


@pytest.fixture()
def tools(sample_csv, tmp_path):
    ds = Dataset(sample_csv)
    return {t.name: t for t in build_data_tools(ds, tmp_path / "out")}


@pytest.mark.asyncio
async def test_dataset_stats(tools):
    out = json.loads(await tools["dataset_stats"].execute())
    assert out["total_rows"] == 6


@pytest.mark.asyncio
async def test_list_top_categories(tools):
    out = json.loads(await tools["list_top_categories"].execute(n=1))
    assert out["categories"][0]["top_category"] == "闹钟"


@pytest.mark.asyncio
async def test_filter_writes_csv(tools):
    out = json.loads(await tools["filter_queries"].execute(keyword="闹钟", limit=100))
    assert out["count"] == 3
    assert out["csv_path"] and os.path.exists(out["csv_path"])


@pytest.mark.asyncio
async def test_sample_random(tools):
    out = json.loads(await tools["sample_queries"].execute(strategy="random", n=4))
    assert out["count"] == 4


@pytest.mark.asyncio
async def test_sample_stratified_top10(tools):
    out = json.loads(await tools["sample_queries"].execute(strategy="stratified_by_category", n=2, top_k=2, per_category=1))
    assert out["count"] == 2


@pytest.mark.asyncio
async def test_get_cluster(tools):
    out = json.loads(await tools["get_cluster"].execute(cluster_id=1))
    assert out["cluster_id"] == 1 and out["rows"] == 3
