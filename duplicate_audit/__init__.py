"""Read-only AI-assisted duplicate-owner auditing."""

from .core import (
    AUDIT_DATASET,
    CANDIDATE_DATASET,
    build_identity_card,
    discover_candidates,
    embedding_views,
    resolve_final_classification,
)

__all__ = [
    "AUDIT_DATASET",
    "CANDIDATE_DATASET",
    "build_identity_card",
    "discover_candidates",
    "embedding_views",
    "resolve_final_classification",
]
