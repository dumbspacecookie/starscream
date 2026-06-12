import hashlib


def assign_split(
    key: str,
    *,
    val_ratio: float = 0.2,
    val_buckets: int = 5,
) -> str:
    """Deterministic train/val split from a grouping key (country, taxonomy, etc.)."""
    if not key:
        key = "_unknown"
    digest = hashlib.sha256(key.encode()).hexdigest()
    bucket = int(digest[:8], 16) % val_buckets
    threshold = int(val_ratio * val_buckets)
    return "val" if bucket < threshold else "train"
