# SPDX-License-Identifier: MIT
"""100% MIT Open-Source Community Integration for LangChain (`langchain-silicium`).

Provides drop-in wrappers around `silicium_json` and `silicium_vector`:
  - `SiliciumJsonLoader` (NDJSON / JSONL streaming document loader)
  - `SiliciumVectorStore` & `SiliciumSemanticCache` (sub-50us L2 / Cosine ANN retrieval)
"""

from __future__ import annotations

from typing import Any


def get_langchain_silicium_components(module: Any) -> dict[str, Any]:
    """Return the drop-in LangChain connectors exposed by a Silicium SDK module."""
    return {
        "SiliciumJsonLoader": getattr(module, "SiliciumJsonLoader", None),
        "SiliciumVectorStore": getattr(module, "SiliciumVectorStore", None),
        "SiliciumSemanticCache": getattr(module, "SiliciumSemanticCache", None),
        "SiliciumLiteLLMGateway": getattr(module, "SiliciumLiteLLMGateway", None),
    }
