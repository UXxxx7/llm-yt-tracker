"""Controlled vocabulary for LLM topic tags.

WHY: free-form LLM tagging produces drift ("RAG" vs "rag" vs "retrieval augmented
generation"). A fixed vocabulary keeps the UI filter usable and makes related-video
grouping meaningful.
"""

CONTROLLED_TAGS = [
    "RAG",
    "fine-tuning",
    "agents",
    "evals",
    "multimodal",
    "MoE",
    "reasoning",
    "inference-optimization",
    "prompting",
    "alignment",
    "open-source-models",
    "benchmarks",
    "scaling",
    "interpretability",
    "robotics",
    "code-generation",
]

UNCATEGORIZED = "uncategorized"

_TAG_SET = set(CONTROLLED_TAGS)


def normalize_tags(raw_tags):
    """Keep only valid tags, dedupe preserving order, cap at 5, fallback to uncategorized."""
    seen = set()
    out = []
    for t in raw_tags:
        if t in _TAG_SET and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= 5:
            break
    return out if out else [UNCATEGORIZED]
