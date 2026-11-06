# SPDX-License-Identifier: MIT
"""Unit tests for LiteLLM `SiliciumAiOpsLogger` integration (`v1.108+`)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Final


class _FakeGateway:
    def __init__(self, pii_policy: str = "mask") -> None:
        self.pii_policy: Final = pii_policy

    def __call__(self, *args: object) -> object:
        if not args:
            return self
        return {"called_args": len(args)}

    def pre_call_hook(
        self,
        request_payload: Any = None,
        raise_on_block: bool = False,
        data: Any = None,
        call_type: Any = None,
    ) -> Mapping[str, Any]:
        if isinstance(data, dict) and call_type is not None:
            return {
                "model": data.get("model", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": "[SILICIUM_REDACTED_EMAIL]"}],
                "metadata": {"silicium_inspection": {"allowed": True, "pii_flags": 4}},
            }
        return {
            "allowed": not raise_on_block,
            "sanitized_payload_str": "[SILICIUM_REDACTED_EMAIL]",
        }

    async def async_pre_call_hook(
        self,
        request_payload: Any = None,
        raise_on_block: bool = False,
        data: Any = None,
        call_type: Any = None,
    ) -> Mapping[str, Any]:
        return self.pre_call_hook(
            request_payload=request_payload,
            raise_on_block=raise_on_block,
            data=data,
            call_type=call_type,
        )

    def post_call_hook(
        self,
        request_payload: Any,
        response_obj: Any = None,
        prompt: str = "",
        end_time: Any = None,
    ) -> Mapping[str, Any]:
        return {"cached": True, "prompt": prompt, "end_time": end_time}

    async def async_log_success_event(
        self,
        kwargs: Any,
        response_obj: Any = None,
        prompt: str = "",
        end_time: Any = None,
    ) -> Mapping[str, Any]:
        return self.post_call_hook(
            kwargs,
            response_obj=response_obj,
            prompt=prompt,
            end_time=end_time,
        )


def test_silicium_ai_ops_logger_4arg_proxy_and_1arg_sdk_contract() -> None:
    from litellm_silicium_integration import SiliciumAiOpsLogger

    logger: Final = SiliciumAiOpsLogger(pii_policy="mask")
    logger._delegate = _FakeGateway(pii_policy="mask")

    assert logger() is logger

    proxy_req: Final = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Email ceo@example.com"}],
    }
    res_4arg: Final = asyncio.run(
        logger.async_pre_call_hook({"api_key": "k"}, None, proxy_req, "completion")
    )
    assert res_4arg["messages"][0]["content"] == "[SILICIUM_REDACTED_EMAIL]"
    assert res_4arg["metadata"]["silicium_inspection"]["allowed"] is True

    res_1arg: Final = asyncio.run(logger.async_pre_call_hook(proxy_req))
    assert res_1arg["allowed"] is True
    assert res_1arg["sanitized_payload_str"] == "[SILICIUM_REDACTED_EMAIL]"

    log_out: Final = asyncio.run(
        logger.async_log_success_event(proxy_req, {"id": "chatcmpl-1"}, 0.0, 0.02)
    )
    assert log_out["cached"] is True
