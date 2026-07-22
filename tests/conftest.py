import pandas as pd
import pytest


@pytest.fixture()
def sample_csv(tmp_path):
    df = pd.DataFrame([
        {"cluster_id": 1, "cluster_size": 3, "top_category": "闹钟", "sub_intent": "设置闹钟", "query_text": "帮我定个闹钟|明天早上7点"},
        {"cluster_id": 1, "cluster_size": 3, "top_category": "闹钟", "sub_intent": "设置闹钟", "query_text": "闹钟响了"},
        {"cluster_id": 1, "cluster_size": 3, "top_category": "闹钟", "sub_intent": "关闭闹钟", "query_text": "关掉闹钟"},
        {"cluster_id": 2, "cluster_size": 2, "top_category": "天气", "sub_intent": "查询天气", "query_text": "今天天气怎么样"},
        {"cluster_id": 2, "cluster_size": 2, "top_category": "天气", "sub_intent": "查询天气", "query_text": "明天会下雨吗"},
        {"cluster_id": -1, "cluster_size": 0, "top_category": "噪声", "sub_intent": "噪声", "query_text": "随便聊聊"},
    ])
    p = tmp_path / "data.csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p
