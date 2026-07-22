from harness.dataset import Dataset


def test_stats(sample_csv):
    ds = Dataset(sample_csv)
    s = ds.stats()
    assert s["total_rows"] == 6
    assert s["n_clusters"] == 3  # 含 -1
    assert s["n_categories"] == 3
    assert s["noise_rows"] == 1


def test_top_categories(sample_csv):
    ds = Dataset(sample_csv)
    top = ds.top_categories(2)
    assert top[0]["top_category"] == "闹钟" and top[0]["rows"] == 3
    assert top[1]["top_category"] == "天气" and top[1]["rows"] == 2


def test_sub_intents_filtered(sample_csv):
    ds = Dataset(sample_csv)
    ints = ds.sub_intents(category="闹钟")
    names = {i["sub_intent"] for i in ints}
    assert names == {"设置闹钟", "关闭闹钟"}


def test_filter_keyword(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.filter(keyword="闹钟")
    assert len(out) == 3


def test_filter_category_and_limit(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.filter(category="闹钟", limit=2)
    assert len(out) == 2


def test_sample_random_count(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.sample(4, strategy="random")
    assert len(out) == 4


def test_sample_stratified_top_k(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.sample(2, strategy="stratified_by_category", top_k=2, per_category=1)
    cats = set(r["top_category"] for r in out)
    assert len(out) == 2 and cats == {"闹钟", "天气"}


def test_sample_caps_at_available(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.sample(999, strategy="random")
    assert len(out) == 6
