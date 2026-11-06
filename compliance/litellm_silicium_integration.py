# SPDX-License-Identifier: MIT
"""LiteLLM CustomLogger integration for Silicium AI Ops (`silicium-ai-ops` / `silicium-json`).

Provides 1-pass SIMD JSON validation, 12-flag PII/Secret guardrails, KV-Cache prefix routing,
and in-process HNSW semantic caching for LiteLLM Proxy (`v1.108+`).
"""

from __future__ import annotations

import contextlib
import importlib
from collections.abc import Mapping
from typing import Any, Final


def _resolve_custom_logger_base() -> type:
    with contextlib.suppress(Exception):
        mod: Final = importlib.import_module("litellm.integrations.custom_logger")
        custom_cls: Final = getattr(mod, "CustomLogger", object)
        if isinstance(custom_cls, type):
            return custom_cls
    return object


class SiliciumAiOpsLogger(_resolve_custom_logger_base()):
    """LiteLLM `CustomLogger` callback delegating to `silicium_ai_ops.SiliciumLiteLLMGateway`."""

    def __init__(
        self,
        num_workers: int = 8,
        max_tokens: int = 262144,
        pii_policy: str = "block",
        enable_semantic_cache: bool = True,
        cache_dim: int = 8,
        cache_distance_threshold: float = 0.15,
        residency_zone: str = "on-prem-sovereign",
    ) -> None:
        with contextlib.suppress(Exception):
            super().__init__()
        eff_workers: Final = max(1, int(num_workers))
        eff_tokens: Final = max(1, int(max_tokens))
        eff_policy: Final = str(pii_policy).strip().lower() or "block"
        eff_cache: Final = bool(enable_semantic_cache)
        eff_dim: Final = max(1, int(cache_dim))
        eff_thresh: Final = float(cache_distance_threshold)
        eff_zone: Final = str(residency_zone)
        self.num_workers: int = eff_workers
        self.max_tokens: int = eff_tokens
        self.pii_policy: str = eff_policy
        self.enable_semantic_cache: bool = eff_cache
        self.cache_dim: int = eff_dim
        self.cache_distance_threshold: float = eff_thresh
        self.residency_zone: str = eff_zone
        self._delegate: Any = None

    def _get_delegate(self) -> Any:
        if self._delegate is not None:
            return self._delegate
        for mod_name in ("silicium_ai_ops", "silicium_json"):
            try:
                mod: Final = importlib.import_module(mod_name)
                gw_cls: Final = getattr(mod, "SiliciumLiteLLMGateway", None)
                if gw_cls is not None:
                    self._delegate = gw_cls(
                        num_workers=self.num_workers,
                        max_tokens=self.max_tokens,
                        pii_policy=self.pii_policy,
                        enable_semantic_cache=self.enable_semantic_cache,
                        cache_dim=self.cache_dim,
                        cache_distance_threshold=self.cache_distance_threshold,
                        residency_zone=self.residency_zone,
                    )
                    return self._delegate
            except Exception:
                continue
        raise RuntimeError(
            "SiliciumAiOpsLogger requires `silicium-ai-ops` or `silicium-json` to be installed."
        )

    def __call__(self, *args: object) -> Any:
        if not args:
            return self
        delegate: Final = self._get_delegate()
        return delegate(*args)

    def pre_call_hook(
        self,
        user_api_key_dict: Any = None,
        cache: Any = None,
        data: Any = None,
        call_type: Any = None,
    ) -> Any:
        delegate: Final = self._get_delegate()
        return delegate.pre_call_hook(
            request_payload=user_api_key_dict,
            raise_on_block=cache if isinstance(cache, bool) else False,
            data=data,
            call_type=call_type,
        )

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any = None,
        cache: Any = None,
        data: Any = None,
        call_type: Any = None,
    ) -> Any:
        delegate: Final = self._get_delegate()
        return await delegate.async_pre_call_hook(
            request_payload=user_api_key_dict,
            raise_on_block=cache if isinstance(cache, bool) else False,
            data=data,
            call_type=call_type,
        )

    def log_success_event(
        self,
        kwargs: Any,
        response_obj: Any = None,
        start_time: Any = "",
        end_time: Any = None,
    ) -> Mapping[str, Any]:
        delegate: Final = self._get_delegate()
        eff_prompt: Final = start_time if isinstance(start_time, str) else ""
        res: Final = delegate.post_call_hook(
            kwargs,
            response_obj=response_obj,
            prompt=eff_prompt,
            end_time=end_time,
        )
        return res

    async def async_log_success_event(
        self,
        kwargs: Any,
        response_obj: Any = None,
        start_time: Any = "",
        end_time: Any = None,
    ) -> Mapping[str, Any]:
        delegate: Final = self._get_delegate()
        eff_prompt: Final = start_time if isinstance(start_time, str) else ""
        res: Final = await delegate.async_log_success_event(
            kwargs,
            response_obj=response_obj,
            prompt=eff_prompt,
            end_time=end_time,
        )
        return res


silicium_ai_ops_logger: Final = SiliciumAiOpsLogger()
