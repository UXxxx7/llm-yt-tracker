from pipeline.tags import CONTROLLED_TAGS, normalize_tags, UNCATEGORIZED


def test_controlled_tags_are_unique_and_lowercase_safe():
    assert len(CONTROLLED_TAGS) == len(set(CONTROLLED_TAGS))
    assert "RAG" in CONTROLLED_TAGS
    assert "fine-tuning" in CONTROLLED_TAGS


def test_normalize_keeps_valid_tags_in_order():
    out = normalize_tags(["RAG", "evals", "agents"])
    assert out == ["RAG", "evals", "agents"]


def test_normalize_drops_unknown_and_caps_at_five():
    out = normalize_tags(["RAG", "not-a-tag", "evals", "agents", "MoE", "scaling", "reasoning"])
    assert "not-a-tag" not in out
    assert len(out) == 5


def test_normalize_returns_uncategorized_when_empty():
    assert normalize_tags([]) == [UNCATEGORIZED]
    assert normalize_tags(["not-a-tag"]) == [UNCATEGORIZED]


def test_normalize_dedupes():
    assert normalize_tags(["RAG", "RAG", "evals"]) == ["RAG", "evals"]
