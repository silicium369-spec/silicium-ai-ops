---
name: "silicium-vector-arena"
description: "Agent-native CLI evaluation harness for silicium-vector-arena (Community Edition, SCSL-1.0). Supports machine-readable JSON output (--json) and deterministic hardware benchmark verification."
---

<skill id="silicium-vector-arena" version="1.0" mode="AGENT_NATIVE_CLI">

# silicium-vector-arena

Agent-native command-line interface and evaluation harness for **silicium-vector-arena**.

- **Developer**: Silicium Architecture Research Team
- **License**: Silicium Community & Evaluation License v1.0 (`SCSL-1.0` — Octa-Shield Edition, SPDX: `LicenseRef-Silicium-Community-1.0`)
- **Patent Notice**: Protected under Patent Pending. All rights reserved.

## Discovery & Machine-Readable Output

Pass `--help`, `host-token [--json]`, `status --json`, `status --prometheus`, `status --otel-json`, or `roi --vectors <N> --dim <D> --json` to inspect commands and emit structured JSON, GenAI OpenTelemetry span attributes, or OpenMetrics telemetry on `stdout`.

## Python SDK & C-ABI Capabilities

- **Python SDK (`silicium_vector`)**: `Index` (`add`, `add_from_ndjson`, `delete_ids`, `search`, `search_json`, `search_range`, `search_mmr`, `deduplicate_semantic`, `save`, `load`, `to_bytes`, `from_bytes`), `SiliciumQG`, `SiliciumHNSW`, `SiliciumLiteLLMGateway` (`pre_call_hook`, `async_pre_call_hook`, `post_call_hook`, `async_log_success_event`, `mask_sensitive_payload`, `litellm_gateway`), `SiliciumLangfuseTracer` (`enrich_langfuse_span`), `generate_litellm_config_yaml`, `cdist`, `hybrid_rrf`, `compute_distance`, `normalize_l2(..., inplace=True)`, `host_token`, `license_status`, `session_quota_status`, `license_info`, `flush_session_quota`, `check_license_health`, `prometheus_metrics`, `otel_span_attributes`, `estimate_finops_roi`, `recommend_slot_for_host`, `get_include`, `get_lib_path`.
- **C-ABI Header (`include/silicium_vector.h`) & Node.js / TypeScript / Bun FFI (`< 1 ms`, `@silicium/ai-ops`)**: Exported C-ABI symbols (`silicium_ann_*`) for zero-copy in-process FFI integration in C/C++, Rust, Go, Java, and Node.js / TypeScript / Bun (`bun:ffi` `dlopen` / `koffi`, `@silicium/ai-ops` `Index` zero-copy `Float32Array` `ptr()`, and `SiliciumVercelAiMiddleware` for the Vercel AI SDK `wrapLanguageModel`).

## 1-Line Framework Drop-In Integrations (`FastAPI`, `LiteLLM`, `Langfuse`, `Vercel AI SDK`, `LangChain`, `LlamaIndex`, `vLLM`, `Instructor`, `Ray Data`, `HuggingFace Datasets`)

Coding agents can wire the zero-copy Drop-In connectors, AI Gateway hooks, and TypeScript middleware across `silicium_vector` and `silicium_json` in 1 line:
- **LangChain & LlamaIndex VectorStore (`SiliciumVectorStore`)**: `SiliciumVectorStore.from_ndjson(ndjson_bytes, dim=1536, text_key='text')` exposing `.similarity_search_by_vector(vec, k=4)`, `.similarity_search_with_score_by_vector(vec, k=4)`, and `.query(vec, similarity_top_k=4)`.
- **LiteLLM & LangChain Semantic Cache (`SiliciumSemanticCache`)**: `SiliciumSemanticCache(dim=8, space='l2', distance_threshold=0.15)` exposing `.set_cache()`, `.get_cache()`, `.async_set_cache()`, `.async_get_cache()`, `.update()`, and `.lookup()`.
- **LiteLLM Proxy CustomLogger & Langfuse OpenTelemetry Tracer (`SiliciumLiteLLMGateway`, `SiliciumLangfuseTracer`)**: `litellm.callbacks = [SiliciumLiteLLMGateway(pii_policy='block', max_tokens=262144)]` (or declarative `litellm_config.yaml` via `generate_litellm_config_yaml()`) and `SiliciumLangfuseTracer.enrich_langfuse_span(span, payload)`.
- **Vercel AI SDK & TypeScript (`@silicium/ai-ops` / `SiliciumVercelAiMiddleware`)**: `wrapLanguageModel({ model, middleware: new SiliciumVercelAiMiddleware({ piiPolicy: 'block', maxTokens: 262144 }) })`.
- **Companion `silicium_json` Drop-In Connectors**: `SiliciumJsonLoader` (LangChain/LlamaIndex), `SiliciumJSONResponse` (FastAPI/Starlette), `SiliciumInstructorAdapter` (Instructor/Pydantic), `SiliciumVllmPrefixRouter` (vLLM/SGLang KV-Cache prefix routing), `SiliciumRayBatchMapper` (Ray Data `map_batches`), and `SiliciumDatasetLoader` (HuggingFace `Dataset.from_dict`).

## Community Hardware Envelope (`SCSL-1.0`) & Production Unlock (`SILICIUM_ENTERPRISE_KEY`)

The Tier 0 Community Edition operates within the single-node evaluation envelope (`1` physical CPU socket, `<= 16` logical threads in `reproduce_all.sh` / `confrontation_arena.py` benchmark harnesses; `<= 8` logical threads, `<= 1,000,000` vectors per index, and a unified `10 GiB` 1-hour rolling session quota in library/Python SDK mode synchronized across `/dev/shm`, `/var/tmp`, and `SILICIUM_SHM_DIR`/`TMPDIR`/`/tmp` with read-only container fallback, `x64` HNSW graph traversal work multiplier, and O(1) benchmark batch deduplication, `Queue-Depth=1`). Setting a signed `56`-character v3 Biometric Passport `SILICIUM_ENTERPRISE_KEY` (`SLCM-S<SLOT>-<VCPUS>-<YYYYMMDD>-<TAG16HEX>-<MAC16HEX>`, bounded by the 13-month sliding horizon `max_sliding_exp_yyyymmdd` and the hard `.so` binary build expiration ceiling `MAX_BINARY_BUILD_EXP_YYYYMMDD = 20271105` via `is_binary_build_expired_at` with `binary_build_exp_yyyymmdd` and `binary_expired` telemetry in `license_status()` / `check_license_health()`, or mounted via `SILICIUM_ENTERPRISE_KEY_FILE` up to `512` bytes for up to `8` stacked keys; `Slot 1: 19 USD/mo` up to `Slot 10: 12,000 USD/mo`, bound to `python3 -m silicium_vector host-token` with Kubernetes Cluster-CA priority, `boot_id`/`cgroup`/`hostname` container fallback, and companion `silicium_json` 12-flag PII/Secret firewall `decode_pii_flags` / `classify_pii_sensitivity` / `build_compliance_audit_record`, see [`SPONSORS.md`](SPONSORS.md)) removes the `10 GiB/h` library session cap and the `1,000,000` vector limit (`<= 16` threads Workstation at Slot 1, and `16` up to `2,560+` vCPUs — `2,560` vCPUs/key at Slot 10: `12,000 USD/mo`, multi-key stackable — for 24/7 commercial production at Slots 2..10 across both `Silicium JSON` and `Silicium Vector`).

</skill>
