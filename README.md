# Silicium AI Ops (`SAO`) — Unified SIMD JSON, HNSW Vector & LLM Guardrail Suite (`x86_64` AVX-512 & AVX2)

> **Launch Status**: **Community Edition Available Now (Free Forever)** & **Indie / Lab Supporter Tier (`19 USD/mo`) Open on GitHub Sponsors** — **Commercial & Enterprise Production Licenses (Slots 2 to 10) Coming Soon**.
> **Silicium AI Ops (`v1.0.2`)**: Unified zero-copy C-ABI, Python (`silicium_ai_ops`, `silicium_json`, `silicium_vector`), and TypeScript/Bun/Node.js (`@silicium/ai-ops`) SDK combining **Silicium JSON** (`9.42 GB/s` 1T / `390 GB/s` MC, `0` malloc, 12-flag SWAR PII/Secret firewall) and **Silicium Vector** (`369,836 QPS` SIFT-1M, `4.0x` SQ8 RAM downsizing, `< 0.1 ms` `mmap` serverless cold-start) — **100% Proprietary Core (Patent Pending, SCSL-1.0)**.

SPDX-License-Identifier: LicenseRef-Silicium-Community-1.0

## Quick Start (1-Line Unified Python Wheel & TypeScript / Bun Tarball)

```bash
# 1. Python 3.10+ (Linux x86_64 — bundles silicium_ai_ops, silicium_json, and silicium_vector + C headers)
uv pip install https://github.com/silicium369-spec/silicium-ai-ops/releases/download/v1.0.2/silicium_ai_ops-1.0.2-py3-none-manylinux_2_28_x86_64.whl

# 2. TypeScript / Bun / Node.js 18+ (@silicium/ai-ops — bun:ffi & koffi zero-copy C-ABI bindings)
bun add https://github.com/silicium369-spec/silicium-ai-ops/releases/download/v1.0.2/silicium-ai-ops-1.0.2.tgz
```

```python
import numpy as np
from silicium_ai_ops import (
    SiliciumLiteLLMGateway,
    SiliciumLangfuseTracer,
    ingest_ndjson_to_vector_arena_zero_copy,
    scan_pii_flags_swar,
    decode_pii_flags,
    license_status,
)
from silicium_json import (
    parse_bytes,
    get_field_str,
    get_field_f64,
    extract_f32_into,
    filter_ndjson_texts,
    SiliciumJSONResponse,
    SiliciumInstructorAdapter,
    SiliciumVllmPrefixRouter,
)
from silicium_vector import (
    SiliciumQG,
    Index,
    SiliciumVectorStore,
    SiliciumSemanticCache,
)

# 1. Zero-Copy 64B-Aligned NDJSON -> HNSW Vector Ingestion & Retrieval (0 Python float lists)
ndjson_rag = (
    b'{"id": 101, "text": "Silicium AVX-512 RAG", "score": 0.98, "embedding": [1.0, 0.0, 0.0, 0.0]}\n'
    b'{"id": 102, "text": "Sub-50us Semantic Cache", "score": 0.95, "embedding": [0.0, 1.0, 0.0, 0.0]}\n'
)
arena = ingest_ndjson_to_vector_arena_zero_copy(ndjson_rag, dim=4, embedding_key="embedding", text_key="text")

# 2. Sub-0.1ms Zero-Copy Serverless Cold-Start (Index.from_bytes / Linux Page Cache mmap)
idx = Index(dim=4, space="cosine", m=16, ef_construction=64)
idx.add(np.eye(4, dtype=np.float32), ids=[100, 101, 102, 103])
blob = idx.to_bytes()
cold_idx = Index.from_bytes(memoryview(blob))  # < 0.1 ms Zero-Copy Serverless Cold-Start
top_ids, top_dists = cold_idx.search(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), k=2, ef=32, return_distances=True)

# 3. 12-Flag SWAR Wire-Speed PII & Secret Firewall (Luhn Credit Card, IBAN MOD-97, JWT, AWS/OpenAI/GitHub Keys)
pii_mask = scan_pii_flags_swar(b'{"prompt": "Contact alice@example.com or key sk-proj-1234567890abcdefghijklmnop"}')
detected_pii = decode_pii_flags(pii_mask)
```

```bash
# Built-in CLI, OpenMetrics/Prometheus Exporter & FinOps Cloud-to-Silicon ROI Calculator
python3 -m silicium_ai_ops status --json
python3 -m silicium_json status --prometheus
python3 -m silicium_vector roi --vectors 10000000 --dim 1536 --json
```

---

## 1-Line Drop-In Connectors Across 10 AI Ops & LLM Frameworks

Drop `silicium_ai_ops`, `silicium_json`, `silicium_vector`, and `@silicium/ai-ops` into your existing stack with zero mandatory framework dependencies at import time and full PEP 561 `.pyi` / TypeScript `.d.ts` typing:

```python
from silicium_ai_ops import SiliciumLiteLLMGateway, SiliciumLangfuseTracer
from silicium_vector import SiliciumVectorStore, SiliciumSemanticCache
from silicium_json import (
    SiliciumJSONResponse,
    SiliciumJsonLoader,
    SiliciumInstructorAdapter,
    SiliciumVllmPrefixRouter,
    SiliciumRayBatchMapper,
    SiliciumDatasetLoader,
)

# 1. LiteLLM Proxy & Gateway — In-process <50us semantic cache + 12-flag SWAR PII/Secret guardrail + KV prefix hash
gateway = SiliciumLiteLLMGateway(dim=4, distance_threshold=0.15, block_pii=False)
inspected = gateway.inspect_and_route(b'{"model":"gpt-4o","messages":[{"role":"user","content":"Hello"}]}')

# 2. Langfuse & OpenTelemetry — Wire-speed client-side PII/Secret scrubbing before telemetry export
tracer = SiliciumLangfuseTracer(redact_pii=True)
safe_span = tracer.scrub_payload(b'{"user_email":"ceo@company.com","messages":[{"role":"user","content":"Hi"}]}')

# 3. Open-WebUI, 4. LangChain & 5. LlamaIndex — 4x RAM downsizing local HNSW VectorStore & SemanticCache
vstore = SiliciumVectorStore.from_ndjson(ndjson_rag, dim=4, text_key="text", space="l2")
sem_cache = SiliciumSemanticCache(dim=4, space="l2", distance_threshold=0.15)

# 6. FastAPI / Starlette (SiliciumJSONResponse), 7. Instructor (SiliciumInstructorAdapter),
# 8. vLLM / SGLang (SiliciumVllmPrefixRouter), 9. Ray Data (SiliciumRayBatchMapper) & 10. HuggingFace Datasets
resp = SiliciumJSONResponse({"status": "ok", "engine": "silicium"}, inspect_llm=True)
routing = SiliciumVllmPrefixRouter(num_workers=8).route_request(b'{"model":"gpt-4o","messages":[{"role":"system","content":"Sys"}]}')
```

### TypeScript / Bun / Node.js (`@silicium/ai-ops` & Vercel AI SDK Middleware)

```typescript
import { SiliciumAiOps, createSiliciumVercelMiddleware } from "@silicium/ai-ops";

const sao = new SiliciumAiOps();
const inspection = sao.inspectLlmRequest('{"model":"gpt-4o","stream":true,"messages":[{"role":"user","content":"Hello"}]}');
const middleware = createSiliciumVercelMiddleware({ blockSecrets: true });
```

---

## 1. Silicium Vector Benchmark Results (AWS `c7a.2xlarge` — AMD EPYC 9R14, Zen 4 AVX-512)

### Multi-Engine 1-vCPU Confrontation (SIFT-128D, `k=10`, `M=16`, `efConstruction=100`, `taskset -c 0`)

- **SIFT-100K 1-vCPU Index Build Time**: **5.24 s** (`Silicium`) vs `5.93 s` (`usearch`), `7.71 s` (`hnswlib`), `9.32 s` (`FAISS`)

| Dataset & `efSearch` | Silicium (`QPS` / `Recall@10`) | `usearch` (`QPS` / `Recall@10`) | `hnswlib` (`QPS` / `Recall@10`) | `FAISS` (`QPS` / `Recall@10`) | Speedup vs `usearch` / `hnswlib` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SIFT-10K** (`ef=12`) | **190,281 QPS** (`0.9931`) | 146,653 QPS (`0.9701`) | 134,801 QPS (`0.9705`) | 135,261 QPS (`0.9689`) | **1.30x** / **1.41x** |
| **SIFT-10K** (`ef=16`) | **155,991 QPS** (`0.9979`) | 122,131 QPS (`0.9867`) | 114,179 QPS (`0.9870`) | 116,216 QPS (`0.9875`) | **1.28x** / **1.37x** |
| **SIFT-10K** (`ef=24`) | **118,027 QPS** (`1.0000`) | 94,813 QPS (`0.9972`) | 89,588 QPS (`0.9971`) | 89,930 QPS (`0.9978`) | **1.24x** / **1.32x** |
| **SIFT-100K** (`ef=16`) | **100,129 QPS** (`0.9223`) | 49,040 QPS (`0.9002`) | 35,582 QPS (`0.9069`) | 33,588 QPS (`0.8885`) | **2.04x** / **2.81x** |
| **SIFT-100K** (`ef=32`) | **55,835 QPS** (`0.9736`) | 29,534 QPS (`0.9696`) | 21,799 QPS (`0.9720`) | 19,595 QPS (`0.9640`) | **1.89x** / **2.56x** |
| **SIFT-100K** (`ef=64`) | **32,187 QPS** (`0.9909`) | 17,466 QPS (`0.9937`) | 13,356 QPS (`0.9917`) | 11,508 QPS (`0.9868`) | **1.84x** / **2.41x** |
| **SIFT-100K** (`ef=128`) | **19,027 QPS** (`0.9963`) | 10,644 QPS (`0.9967`) | 8,385 QPS (`0.9975`) | 6,968 QPS (`0.9985`) | **1.79x** / **2.27x** |

### Official SIFT-1M Full-Scale Evaluation (1,000,000 vectors, 128D, 10,000 queries, `k=10`)

| `ef` | `Recall@10` (`balanced` `M=24`) | 1-Core / 8-Core `QPS` (`balanced`) | 1-Core `P50` / `P99` (`balanced`) | `Recall@10` (`fast_stream` `M=16`) | 1-Core / 8-Core `QPS` (`fast_stream`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `16` | **0.8569** (`+9.51%`) | **39,540 QPS** / **294,476 QPS** | `24.91µs` / `40.45µs` | `0.7618` | **49,261 QPS** / **369,836 QPS** |
| `24` | **0.9078** (`+7.75%`) | **29,404 QPS** / **219,191 QPS** | `33.89µs` / `50.81µs` | `0.8303` | **36,902 QPS** / **278,597 QPS** |
| `32` | **0.9362** (`+6.44%`) | **23,549 QPS** / **175,582 QPS** | `42.70µs` / `60.07µs` | `0.8718` | **29,787 QPS** / **224,878 QPS** |
| `64` | **0.9777** (`+3.52%`) | **13,260 QPS** / **99,105 QPS** | `77.21µs` / `99.48µs` | `0.9425` | **17,101 QPS** / **128,433 QPS** |
| `128` | **0.9936** (`+1.49%`) | **7,316 QPS** / **54,599 QPS** | `140.86µs` / `174.26µs` | `0.9787` | **9,374 QPS** / **71,169 QPS** |
| `256` | **0.9981** (`+0.52%`) | **3,925 QPS** / **29,393 QPS** | `262.42µs` / `322.18µs` | `0.9929` | **5,048 QPS** / **38,223 QPS** |

### High-Dimensional Embeddings (`OpenAI-1536D` & `Cohere-768D`, `4.0x` SQ8 Primary RAM Compression)

| Workload & Metric (`M=24, efC=160`) | `ef` | `Recall@10` | 1-Core `QPS` (`P50` / `P99`) | 8-Core `QPS` (`Speedup`) | Build (`SQ8` vs `FP32`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OpenAI-1536D** (`Cosine`) | `16` | **0.9761** | **19,935 QPS** (`46.8µs` / `85.3µs`) | **145,480 QPS** (**3.50x**) | `0.999s` vs `3.811s` (**3.81x**) |
| **OpenAI-1536D** (`Cosine`) | `32` | **0.9930** | **13,626 QPS** (`70.8µs` / `119.4µs`) | **101,774 QPS** (**3.32x**) | `0.999s` vs `3.811s` (**3.81x**) |
| **OpenAI-1536D** (`Cosine`) | `64` | **1.0000** | **10,322 QPS** (`93.1µs` / `149.6µs`) | **77,854 QPS** (**3.35x**) | `0.999s` vs `3.811s` (**3.81x**) |
| **Cohere-768D** (`Dot`) | `16` | **0.9746** | **42,351 QPS** (`22.7µs` / `41.6µs`) | **312,248 QPS** (**3.20x**) | `0.585s` vs `1.681s` (**2.87x**) |
| **Cohere-768D** (`Dot`) | `32` | **0.9930** | **26,544 QPS** (`35.8µs` / `63.1µs`) | **194,587 QPS** (**2.41x**) | `0.585s` vs `1.681s` (**2.87x**) |
| **Cohere-768D** (`Dot`) | `64` | **0.9980** | **18,729 QPS** (`51.2µs` / `84.7µs`) | **141,861 QPS** (**2.49x**) | `0.585s` vs `1.681s` (**2.87x**) |

---

## 2. Silicium JSON Benchmark Results (AWS `c7a.24xlarge` — AMD EPYC 9R14, 96 Physical Cores)

### Single-Core Hardware PMU Efficiency (`cyc/B`, `ins/B`, `IPC` vs `simdjson::dom` & `simdjson::ondemand`)

| Workload (`Size`) | Silicium 1T | `cyc/B` & `ins/B` | `IPC` (Branchless) | `simdjson` (DOM / OnDemand) | Speedup (vs OD / DOM) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GSOC 2018** (`3.17 MB`) | **7.34–7.58 GB/s** | **0.46 cyc/B** / `1.43 ins/B` | **3.13** | `5.14` / `6.42 GB/s` | **1.18x** / **1.47x** |
| **Clickstream NDJSON** (`0.26 MB`) | **4.80 GB/s** | **0.70 cyc/B** / `3.12 ins/B` | **4.47** | `2.79` / `3.58 GB/s` | **1.34x** / **1.72x** |
| **SemanticScholar** (`8.20 MB`) | **4.10 GB/s** | **0.82 cyc/B** / `2.69 ins/B` | **3.27** | `2.58` / `3.36 GB/s` | **1.22x** / **1.59x** |
| **Twitter Timeline** (`0.60 MB`) | **3.82 GB/s** | **0.96 cyc/B** / `3.83 ins/B` | **4.01** | `2.72` / `3.21 GB/s` | **1.19x** / **1.40x** |
| **CITM Catalog** (`1.65 MB`) | **3.18 GB/s** | **1.15 cyc/B** / `4.83 ins/B` | **4.20** | `2.88` / `3.05 GB/s` | **1.04x** / **1.10x** |
| **Twitter Escaped** (`0.54 MB`) | **2.72 GB/s** | **1.34 cyc/B** / `5.99 ins/B` | **4.46** | `1.29` / `2.38 GB/s` | **1.14x** / **2.11x** |
| **CityLots SF** (`180.99 MB`) | **1.30 GB/s** | **2.59 cyc/B** / `9.72 ins/B` | **3.75** | `0.88` / `0.99 GB/s` | **1.31x** / **1.48x** |

### Multi-Core Scaling (`Full-Decode + IEEE-754 f64` vs `Structural Validation & Index`) & Tail Latency Jitter

| Workload (`Size`) | Full-Decode + `f64` (MC) | Structural Validation & Index (MC) | P50 Latency (µs) | `P99.9 / P50` Jitter |
| :--- | :---: | :---: | :---: | :---: |
| **SemanticScholar** (`8.20 MB`) | **276.64 GB/s** | **352.69 GB/s** | `24.36 µs` | `1.02x` (`0 Malloc`) |
| **GSOC 2018** (`3.17 MB`) | **182.73 GB/s** | **203.03 GB/s** | `16.39 µs` | `1.02x` (`0 Malloc`) |
| **CITM Catalog** (`1.65 MB`) | **164.86 GB/s** | **235.51 GB/s** | `7.33 µs` | `1.02x` (`0 Malloc`) |
| **CityLots SF** (`180.99 MB`) | **97.45 GB/s** | **390.75 GB/s** | `485.68 µs` | `1.02x` (`0 Malloc`) |
| **Twitter Timeline** (`0.60 MB`) | **94.42 GB/s** | **125.90 GB/s** | `5.02 µs` | `1.02x` (`0 Malloc`) |
| **Clickstream NDJSON** (`0.26 MB`) | **68.82 GB/s** | **94.93 GB/s** | `2.92 µs` | `1.02x` (`0 Malloc`) |

---

## Benchmark Reproduction (`reproduce_all.sh` & `silicium_json_bench`)

```bash
# 1. Verify cryptographic SHA-256 digests of all repository files
sha256sum -c checksums.sha256

# 2. Run unified JSON + HNSW Vector reproduction harness
./reproduce_all.sh

# 3. Run standalone JSON CLI benchmark (--json for agent-native output)
./bin/silicium_json_bench --json

# 4. Run full TexMex SIFT-1M or High-Dimensional (768D/1536D) confrontation
./reproduce_all.sh --sift1m
./reproduce_all.sh --high-dim
```

---

## Licensing, Sole IP Ownership & FinOps Tiers (`SPONSORS.md`)

- **Sole & Exclusive IP Ownership (`CLA.md`, `PATENTS.md`, `LICENSE`)**: All rights, title, and interest in and to the Silicium engines, precompiled binaries, C-ABI specifications, and pending patents (**Protected under Patent Pending. All rights reserved.**) are the sole and exclusive property of the Silicium Architecture Research Team (`Maintainer / Licensor`). See [`CLA.md`](CLA.md) and [`PATENTS.md`](PATENTS.md).
- **Community Edition (`0 USD / month` — Free Forever)**: Tier 0 Community Edition is and will remain **free forever** for local evaluation, academic research, CI testing, and benchmark reproduction (`<= 16` threads in benchmark CLI harnesses; `<= 8` threads, `<= 1,000,000` vectors per index, and unified `10 GiB` 1-hour rolling quota with non-destructive soft-landing in library/SDK mode) under Silicium Community & Evaluation License v1.0 (`SCSL-1.0`, `LicenseRef-Silicium-Community-1.0`, Patent Pending).
- **Indie / Lab Supporter Tier (`19 USD / month` — Open Now on GitHub Sponsors) & Enterprise Production Licenses (Slots 2 to 10 — Coming Soon)**: Support the project and unlock Slot 1 (`16` vCPUs, unlimited 24/7 non-commercial & academic lab runs) today via [GitHub Sponsors](https://github.com/sponsors/silicium369-spec). Commercial production licenses (`Slots 2 to 10`: `149 USD/mo` to `12,000 USD/mo`, priced at `20%` of cloud compute/RAM savings = `5.0x` guaranteed ROI) are coming soon. See [`SPONSORS.md`](SPONSORS.md) and [`LICENSE`](LICENSE).
