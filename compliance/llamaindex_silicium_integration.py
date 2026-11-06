# SPDX-License-Identifier: MIT
"""100% MIT Open-Source Community Integration for LlamaIndex (`llamaindex-silicium`).

Provides zero-copy NDJSON ingestion (`ingest_ndjson_to_vector_arena_zero_copy`) and
sub-50us HNSW vector store retrieval for LlamaIndex RAG pipelines.
"""

from __future__ import annotations

from typing import Any


def get_llamaindex_silicium_components(module: Any) -> dict[str, Any]:
    """Return the drop-in LlamaIndex RAG connectors exposed by a Silicium SDK module."""
    return {
        "SiliciumVectorStore": getattr(module, "SiliciumVectorStore", None),
        "SiliciumDatasetLoader": getattr(module, "SiliciumDatasetLoader", None),
        "ingest_ndjson_to_vector_arena_zero_copy": getattr(
            module, "ingest_ndjson_to_vector_arena_zero_copy", None
        ),
    }
