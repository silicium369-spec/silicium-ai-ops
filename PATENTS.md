# Statutory Patent & Intellectual Property Notice

SPDX-License-Identifier: LicenseRef-Silicium-Community-1.0

Protected under Patent Pending (including international patent applications and PCT counterparts). All rights reserved.

## 1. Express Patent Exclusion (Zero Implied Patent Grant)

Nothing in the **Silicium Community & Evaluation Software License 1.0 (`SCSL-1.0` / `LicenseRef-Silicium-Community-1.0`)** grants any express or implied license, immunity, or right under any patent or patent application covering:
- Lock-free Compressed Sparse Row (CSR) HNSW graph traversal with quantized distance accumulation and zero heap allocation on the query hot path (`malloc = 0`);
- Multi-tier scalar and vector quantization with exact top-pool reranking and cache-line prefetching;
- Closed-loop hardware telemetry calibration and multi-socket NUMA scheduling.

## 2. Horizontal Bi-Edition Boundary

- **Tier 0 Community Single-Node Edition (`libsilicium_ann_x86_64.so` + Open Evaluation Harness `reproduce_all.sh`)**:
  Licensed under `LicenseRef-Silicium-Community-1.0` (`LICENSE`) for non-commercial benchmark verification on a single workstation or single-node evaluation instance (`1` physical CPU socket, `<= 16` logical threads in benchmark CLI; `<= 8` logical threads, `<= 1,000,000` vectors per index, and `10 GiB/hour` rolling session quota in library/C-ABI/Python SDK mode, `Queue-Depth=1`).
- **Enterprise Datacenter & Forge Edition (`SILICIUM_ENTERPRISE_KEY` Slots `S01..S10` & Distributed Vector Suite)**:
  Requires a commercial **Silicium Enterprise License** (`SILICIUM_ENTERPRISE_KEY` offline cryptographic gate, `19 USD/mo` to `12,000 USD/mo`, see [`SPONSORS.md`](SPONSORS.md)) for 24/7 commercial production, Dark Compute batch pipelines, multi-socket NUMA servers (`16` to `2,560+` vCPUs, multi-key stackable at Slot 10), and custom hardware compilation.

## 3. Defensive Patent Revocation

Any patent assertion, litigation, or administrative validity challenge initiated against the Licensor or the Software triggers immediate and retroactive termination of all software and evaluation grants pursuant to **SHIELD 5** and **SHIELD 2** of `LICENSE`.
