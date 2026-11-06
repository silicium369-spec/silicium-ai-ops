from __future__ import annotations
# Silicium Architecture Research Team - HNSW & Quantized Graph Vector Search Engine
# Bi-Compliant with VIBE (vector-index-bench/vibe) and ann-benchmarks BaseANN Interface

import argparse
import atexit
import ctypes
import hashlib
import json
import os
import struct
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

try:
    from ..base.module import BaseANN
except (ImportError, ValueError):
    try:
        from vibe.algorithms.base.module import BaseANN
    except ImportError:
        try:
            from ann_benchmarks.algorithms.base.module import BaseANN
        except ImportError:
            class BaseANN:  # type: ignore[no-redef]
                """Fallback BaseANN interface when running in standalone mode."""
                def done(self) -> None: pass
                def get_memory_usage(self) -> Optional[float]: return None
                def get_additional(self) -> Dict[str, Any]: return {}
                def fit(self, X: np.ndarray) -> None: pass
                def query(self, q: np.ndarray, n: int) -> List[int]: return []
                def batch_query(self, X: np.ndarray, n: int) -> Any: pass
                def get_batch_results(self) -> Any: return getattr(self, "res", None)
                def __str__(self) -> str: return getattr(self, "name", "BaseANN")


ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED: int = -2
COMMUNITY_LIB_SESSION_QUOTA_BYTES: int = 10 * 1024 * 1024 * 1024
MIN_VALID_BUILD_YYYYMMDD: int = 20261103
MAX_BINARY_BUILD_EXP_YYYYMMDD: int = 20271105
TIER0_MAX_INDEX_VECTORS: int = 1000000
SPONSORS_URL: str = "https://github.com/sponsors/silicium369-spec"

RECOMMENDED_SLOTS: List[Tuple[int, int, int, int, str]] = [
    (1, 16, 1, 19, "Indie & Lab Workstation (Non-Commercial)"),
    (2, 16, 5, 149, "Micro-Prod Commercial 24/7"),
    (3, 32, 25, 279, "Seed Startup"),
    (4, 64, 50, 499, "Series A FinOps"),
    (5, 128, 100, 949, "Growth Cluster"),
    (6, 256, 250, 1799, "Scale-Up Data Fleet"),
    (7, 512, 500, 3299, "Mid-Market Infra"),
    (8, 1024, 1000, 5999, "Enterprise Core"),
    (9, 2048, 2500, 9999, "Corporate Fleet"),
    (10, 2560, 5000, 12000, "Corporate Max (Multi-Key Stackable, 2,560 vCPUs/key @ 4.69 USD/vCPU)"),
]


class SiliciumQuotaExceededError(RuntimeError):
    """Raised when the 10 GiB/hour Community Edition library session quota or 1M vector cap is exceeded without SILICIUM_ENTERPRISE_KEY."""

    def __init__(self, message: Optional[str] = None) -> None:
        default_msg = (
            "Silicium Community Edition 10 GiB/hour library session quota or 1,000,000-vector cap exceeded "
            f"(ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED = {ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED}). "
            "To unlock unlimited 24/7 production throughput, >1M vectors, and up to 2,560+ vCPUs (Slots 1..10: $19 to $12,000/mo) across "
            "Silicium JSON + Silicium Vector, set SILICIUM_ENTERPRISE_KEY via GitHub Sponsors: "
            f"{SPONSORS_URL}"
        )
        super().__init__(message or default_msg)


def is_binary_build_expired_at(today_yyyymmdd: int = 0) -> bool:
    """Returns True if today_yyyymmdd exceeds the compiled binary's hard expiration horizon MAX_BINARY_BUILD_EXP_YYYYMMDD (20271105)."""
    import datetime

    eff = int(today_yyyymmdd) if int(today_yyyymmdd) > 0 else int(datetime.date.today().strftime("%Y%m%d"))
    return eff < MIN_VALID_BUILD_YYYYMMDD or eff > MAX_BINARY_BUILD_EXP_YYYYMMDD


def _locate_shared_library() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for env_k in ("SILICIUM_LIB_PATH", "SILICIUM_ANN_LIB"):
        env_v = os.environ.get(env_k)
        if env_v and os.path.exists(env_v):
            return env_v
    for local_cand in (
        os.path.join(script_dir, "libsilicium_vector_x86_64.so"),
        os.path.join(script_dir, "libsilicium_ann_x86_64.so"),
        os.path.join(script_dir, "silicium_vector", "libsilicium_vector_x86_64.so"),
        os.path.join(script_dir, "silicium_vector", "libsilicium_ann_x86_64.so"),
    ):
        if os.path.exists(local_cand):
            return local_cand
    release_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "forge", "target", "release"))
    dist_so = os.path.abspath(os.path.join(script_dir, "..", "dist", "libsilicium_ann_x86_64.so"))
    cargo_so: Optional[str] = None
    if os.path.isdir(release_dir):
        for fn in sorted(os.listdir(release_dir)):
            if fn.startswith("lib") and fn.endswith(".so"):
                cargo_so = os.path.join(release_dir, fn)
                break
    if cargo_so and os.path.isfile(cargo_so) and os.path.isfile(dist_so):
        if os.path.getmtime(cargo_so) >= os.path.getmtime(dist_so):
            return cargo_so
        return dist_so
    if cargo_so and os.path.isfile(cargo_so):
        return cargo_so
    if os.path.isfile(dist_so):
        return dist_so
    candidate_paths = [
        os.path.join(script_dir, "bin", "libsilicium_vector_x86_64.so"),
        os.path.join(script_dir, "bin", "libsilicium_ann_x86_64.so"),
        os.path.join(script_dir, "lib", "libsilicium_ann_x86_64.so"),
        os.path.join(script_dir, "..", "lib", "libsilicium_ann_x86_64.so"),
        "/usr/local/lib/libsilicium_ann_x86_64.so",
        "/usr/lib/libsilicium_ann_x86_64.so",
        "/home/app/bin/libsilicium_ann_x86_64.so",
        "/home/app/libsilicium_ann_x86_64.so",
        os.path.join(script_dir, "libann_benchmarks_optimized.so"),
    ]
    for p in candidate_paths:
        if p and os.path.exists(p):
            return p
    dl_script = os.path.join(script_dir, "scripts", "download_release.sh")
    dl_target = os.path.join(script_dir, "lib", "libsilicium_ann_x86_64.so")
    if os.path.isfile(dl_script):
        import subprocess

        try:
            subprocess.run(
                ["bash", dl_script, "ann-v1.0.0", os.path.join(script_dir, "lib")],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if os.path.isfile(dl_target):
                return dl_target
        except Exception:
            pass
    return "libsilicium_ann_x86_64.so"


_GLOBAL_LIB: Optional[ctypes.CDLL] = None


def _get_global_lib() -> ctypes.CDLL:
    global _GLOBAL_LIB
    if _GLOBAL_LIB is None:
        _GLOBAL_LIB = ctypes.CDLL(_locate_shared_library())
    return _GLOBAL_LIB


def flush_session_quota() -> int:
    """Flushes any pending thread-local session quota delta to /dev/shm."""
    try:
        lib = _get_global_lib()
        fn = getattr(lib, "silicium_ann_flush_session_quota", None)
        if fn is not None:
            fn.argtypes = []
            fn.restype = ctypes.c_size_t
            return int(fn())
    except Exception:
        pass
    return 0


def reset_session_quota() -> int:
    """Resets the session quota counter when authorized by an Enterprise key or EAB reset key."""
    try:
        lib = _get_global_lib()
        fn = getattr(lib, "silicium_ann_reset_session_quota", None)
        if fn is not None:
            fn.argtypes = []
            fn.restype = ctypes.c_int32
            return int(fn())
    except Exception:
        pass
    return -1


atexit.register(flush_session_quota)


def get_include() -> str:
    """Returns the absolute directory path containing the C/C++ header silicium_vector.h."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_inc = os.path.join(base_dir, "include")
    if os.path.isdir(local_inc):
        return local_inc
    dist_inc = os.path.join(os.path.dirname(base_dir), "dist", "include")
    if os.path.isdir(dist_inc):
        return dist_inc
    return local_inc


def get_lib_path() -> str:
    """Returns the absolute path to the native shared library (.so) for C/C++/Rust/Go FFI linking."""
    return os.path.abspath(_locate_shared_library())


def _days_between_yyyymmdd(start_yyyymmdd: int, end_yyyymmdd: int) -> int:
    import datetime

    try:
        d0 = datetime.date(start_yyyymmdd // 10000, (start_yyyymmdd // 100) % 100, start_yyyymmdd % 100)
        d1 = datetime.date(end_yyyymmdd // 10000, (end_yyyymmdd // 100) % 100, end_yyyymmdd % 100)
        return int((d1 - d0).days)
    except Exception:
        return 0


def estimate_finops_roi(
    vectors: int = 1000000,
    dim: int = 1536,
    vcpus: int = 64,
    nodes: int = 1,
    gb_per_hour: float = 0.0,
    gb_per_day: float = 0.0,
) -> Dict[str, Any]:
    """Calculates memory footprint and recommends the optimal GitHub Sponsors Enterprise Slot."""
    req_vcpus = max(1, int(vcpus))
    req_nodes = max(1, int(nodes))
    rec_slot, rec_vcpus, rec_nodes, rec_price, rec_label = RECOMMENDED_SLOTS[-1]
    keys_required = 1
    for s_id, s_vcpus, s_nodes, s_price, s_label in RECOMMENDED_SLOTS:
        if s_vcpus >= req_vcpus and s_nodes >= req_nodes:
            rec_slot, rec_vcpus, rec_nodes, rec_price, rec_label = s_id, s_vcpus, s_nodes, s_price, s_label
            break
    else:
        keys_required = max((req_vcpus + rec_vcpus - 1) // rec_vcpus, (req_nodes + rec_nodes - 1) // rec_nodes)
        rec_vcpus = rec_vcpus * keys_required
        rec_nodes = rec_nodes * keys_required
        rec_price = rec_price * keys_required
    raw_bytes = int(vectors) * int(dim) * 4
    sq8_bytes = int(vectors) * int(dim)
    eff_gb_h = float(gb_per_day) / 24.0 if float(gb_per_day) > 0.0 else float(gb_per_hour)
    eff_gb_d = float(gb_per_day) if float(gb_per_day) > 0.0 else float(gb_per_hour) * 24.0
    annual_usd = rec_price * 12
    aws_infra_monthly_savings_usd = rec_price * 5
    net_client_monthly_gain_usd = aws_infra_monthly_savings_usd - rec_price
    managed_api_monthly_usd = int(
        max(
            float(aws_infra_monthly_savings_usd),
            round(eff_gb_d * 30.0 * 0.45 + int(vectors) / 10000.0 * 2.5),
        )
    )
    annual_savings_vs_managed_api_usd = max(0, (managed_api_monthly_usd * 12) - annual_usd)
    return {
        "engine": "silicium-vector",
        "vectors": int(vectors),
        "dim": int(dim),
        "gb_per_hour": round(eff_gb_h, 3),
        "gb_per_day": round(eff_gb_d, 3),
        "requested_vcpus": req_vcpus,
        "requested_nodes": req_nodes,
        "recommended_slot": rec_slot,
        "keys_required": keys_required,
        "multi_key_stackable": True,
        "slot_label": rec_label,
        "slot_max_vcpus": rec_vcpus,
        "slot_max_nodes": rec_nodes,
        "monthly_price_usd": rec_price,
        "annual_price_usd": annual_usd,
        "pricing_model": "Flat-Rate Hardware-Bound Per-vCPU (Zero Per-Token / Zero Per-Query Surprises)",
        "air_gapped_compliance": "100% Self-Hosted Offline HMAC-SHA256 (Zero External Telemetry / EU AI Act & FinTech Ready)",
        "estimated_aws_infra_monthly_savings_usd": aws_infra_monthly_savings_usd,
        "net_client_monthly_gain_usd": net_client_monthly_gain_usd,
        "finops_roi_multiplier": 5.0,
        "active_throughput_scaling_multiplier": "2.5x-3.8x",
        "vector_ram_density_multiplier": 4.0,
        "marginal_cost_per_extra_tenant_usd": 0,
        "estimated_managed_api_monthly_usd": managed_api_monthly_usd,
        "annual_savings_vs_managed_api_usd": annual_savings_vs_managed_api_usd,
        "raw_fp32_gib": round(raw_bytes / (1024**3), 3),
        "sq8_routing_gib": round(sq8_bytes / (1024**3), 3),
        "serverless_cold_start_ms": "< 0.1 ms (Zero-Copy Index.from_bytes / mmap vs 5,000-30,000 ms legacy pointer deserialization)",
        "multi_worker_mmap_sharing": "16x-32x Zero-Copy Linux Page Cache sharing across workers",
        "serverless_tenant_density_multiplier": 16.0,
        "sponsors_url": SPONSORS_URL,
    }


recommend_slot_for_host = estimate_finops_roi

def host_token() -> str:
    try:
        lib = _get_global_lib()
        fn = getattr(lib, "silicium_ann_host_token_c", None)
        if fn is not None:
            fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            fn.restype = ctypes.c_int32
            buf = ctypes.create_string_buffer(32)
            n = int(fn(ctypes.cast(buf, ctypes.c_void_p), 32))
            if n == 21:
                return buf.raw[:21].decode("ascii", errors="ignore")
    except Exception:
        pass
    return "HOST-882CA4C0AA035C0D"


def _as_c_buffer(payload: Any) -> Tuple[Any, int, Any]:
    if isinstance(payload, bytes):
        return payload, len(payload), payload
    if isinstance(payload, str):
        b = payload.encode("utf-8")
        return b, len(b), b
    if isinstance(payload, bytearray):
        n = len(payload)
        if n == 0:
            return b"", 0, payload
        c_buf = (ctypes.c_char * n).from_buffer(payload)
        return c_buf, n, (payload, c_buf)
    try:
        mv = payload if isinstance(payload, memoryview) else memoryview(payload)
    except (BufferError, ValueError):
        mv = None
    if mv is not None and mv.contiguous:
        n = mv.nbytes
        if n == 0:
            return b"", 0, mv
        if not mv.readonly:
            c_buf = (ctypes.c_char * n).from_buffer(mv)
            return c_buf, n, (payload, mv, c_buf)
        u8_view = np.frombuffer(mv, dtype=np.uint8)
        c_ptr = ctypes.cast(u8_view.ctypes.data, ctypes.c_char_p)
        return c_ptr, n, (payload, mv, u8_view)
    F_CONTIGUOUS = bool(getattr(getattr(payload, "flags", None), "f_contiguous", False))
    contig_u8 = np.ascontiguousarray(payload).view(np.uint8).ravel()
    n_bytes = int(contig_u8.nbytes)
    if n_bytes == 0:
        return b"", 0, (contig_u8, F_CONTIGUOUS)
    c_ptr = ctypes.cast(contig_u8.ctypes.data, ctypes.c_char_p)
    return c_ptr, n_bytes, (payload, contig_u8, F_CONTIGUOUS)


def _resolve_active_license_watermark(s_val: int) -> Tuple[str, str, str]:
    htok = host_token()
    if s_val <= 0:
        return htok, "TIER0-COMMUNITY", "community-tier0"
    raw_key = os.environ.get("SILICIUM_ENTERPRISE_KEY", "").strip()
    if not raw_key:
        kf = os.environ.get("SILICIUM_ENTERPRISE_KEY_FILE", "").strip()
        if kf:
            try:
                with open(kf, "rb") as fh:
                    lines = [
                        ln.strip()
                        for ln in fh.read(512).decode("utf-8", errors="ignore").splitlines()
                        if ln.strip() and not ln.strip().startswith("#")
                    ]
                raw_key = ",".join(lines)
            except OSError:
                raw_key = ""
    first_tok = ""
    for sep_tok in raw_key.replace(";", ",").replace("+", ",").replace("\n", ",").split(","):
        if sep_tok.strip():
            first_tok = sep_tok.strip()
            break
    parts = first_tok.split("-")
    if len(parts) == 6:
        return htok, f"BIO-{parts[4].upper()}", "v3-biometric-cluster-bound"
    if len(parts) == 5:
        return htok, f"V2-{parts[4][:8].upper()}", "v2-time-bound"
    return htok, f"V1-SLOT{s_val:02d}", "v1-legacy"


def license_status(today_yyyymmdd: int = 0) -> Dict[str, Any]:
    """Returns O(1) telemetry on the active license slot, vCPU cap, quota usage, and SIMD ISA level."""
    host_vcpus = max(1, os.cpu_count() or 1)
    rec = estimate_finops_roi(vcpus=host_vcpus, nodes=1)
    rec_slot = int(rec["recommended_slot"])
    rec_price = int(rec["monthly_price_usd"])
    bin_exp = bool(is_binary_build_expired_at(today_yyyymmdd))
    lib = _get_global_lib()
    fn = getattr(lib, "silicium_ann_license_status_c", None)
    if fn is not None:
        fn.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        fn.restype = ctypes.c_int32
        slot_id = ctypes.c_uint32(0)
        max_vcpus = ctypes.c_size_t(8)
        exp_date = ctypes.c_uint32(0)
        used_b = ctypes.c_size_t(0)
        limit_b = ctypes.c_size_t(COMMUNITY_LIB_SESSION_QUOTA_BYTES)
        isa_lvl = ctypes.c_uint32(1)
        fn(
            int(today_yyyymmdd),
            ctypes.byref(slot_id),
            ctypes.byref(max_vcpus),
            ctypes.byref(exp_date),
            ctypes.byref(used_b),
            ctypes.byref(limit_b),
            ctypes.byref(isa_lvl),
        )
        s_val = int(slot_id.value)
        eff_vcpus = int(max_vcpus.value)
        used_int = int(used_b.value)
        limit_int = int(limit_b.value)
        isa_str = {2: "AVX-512", 1: "AVX2"}.get(int(isa_lvl.value), "Scalar")
    else:
        fn_eff = getattr(lib, "silicium_ann_effective_max_threads_at", None)
        eff_vcpus = 8
        if fn_eff is not None:
            fn_eff.argtypes = [ctypes.c_uint32]
            fn_eff.restype = ctypes.c_size_t
            eff_vcpus = int(fn_eff(int(today_yyyymmdd or 20261104)))
        s_val = 0 if eff_vcpus <= 8 else 4
        exp_date = ctypes.c_uint32(0)
        used_int = 0
        limit_int = COMMUNITY_LIB_SESSION_QUOTA_BYTES if s_val == 0 else 0
        isa_str = "AVX-512"
    throttled = max(0, host_vcpus - eff_vcpus)
    rem_bytes = max(0, limit_int - used_int) if s_val == 0 else 0
    quota_pct = 0.0 if s_val > 0 or limit_int <= 0 else min(100.0, round((used_int / float(limit_int)) * 100.0, 4))
    nudge = (
        f"Unlock all {host_vcpus} host vCPUs, unlimited 24/7 quota, and >1M vectors with Slot {rec_slot} (${rec_price}/mo): {SPONSORS_URL}"
        if s_val == 0
        else ""
    )
    htok, ltag, bmode = _resolve_active_license_watermark(s_val)
    return {
        "engine": "silicium-vector",
        "slot_id": s_val,
        "tier": "Community Tier 0" if s_val == 0 else f"Enterprise Slot {s_val}",
        "host_vcpus": host_vcpus,
        "max_vcpus": eff_vcpus,
        "throttled_vcpus": throttled,
        "is_cpu_throttled": bool(throttled > 0),
        "max_index_vectors": TIER0_MAX_INDEX_VECTORS if s_val == 0 else None,
        "exp_yyyymmdd": int(exp_date.value),
        "binary_build_exp_yyyymmdd": MAX_BINARY_BUILD_EXP_YYYYMMDD,
        "binary_expired": bin_exp,
        "session_bytes_used": used_int,
        "session_bytes_limit": limit_int,
        "session_bytes_remaining": rem_bytes,
        "quota_used_pct": quota_pct,
        "recommended_slot": rec_slot,
        "recommended_slot_price_usd": rec_price,
        "upgrade_nudge": nudge,
        "isa": isa_str,
        "host_token": htok,
        "license_tag": ltag,
        "binding_mode": bmode,
        "sponsors_url": SPONSORS_URL,
    }


session_quota_status = license_status
license_info = license_status


def check_license_health(min_days_remaining: int = 7, today_yyyymmdd: int = 0) -> Dict[str, Any]:
    """Evaluates license expiry, remaining TTL days, and session quota health for production alerting."""
    import datetime

    eff_today = int(today_yyyymmdd) if today_yyyymmdd > 0 else int(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
    st = license_status(today_yyyymmdd=eff_today)
    slot_id = int(st["slot_id"])
    exp = int(st["exp_yyyymmdd"])
    used = int(st["session_bytes_used"])
    limit = int(st["session_bytes_limit"])
    bin_exp = bool(is_binary_build_expired_at(eff_today))
    if slot_id > 0 and exp > 0 and not bin_exp and exp <= MAX_BINARY_BUILD_EXP_YYYYMMDD:
        days_rem = _days_between_yyyymmdd(eff_today, exp)
        healthy = days_rem >= int(min_days_remaining)
    elif slot_id > 0:
        days_rem = 0
        healthy = False
    else:
        days_rem = 0
        healthy = (used < limit) and not bin_exp
    return {
        "valid": bool(healthy),
        "healthy": bool(healthy),
        "slot_id": slot_id,
        "tier": st["tier"],
        "max_vcpus": int(st["max_vcpus"]),
        "exp_yyyymmdd": exp,
        "days_remaining": int(days_rem),
        "min_days_remaining": int(min_days_remaining),
        "session_bytes_used": used,
        "session_bytes_limit": limit,
        "quota_utilization_ratio": round(used / max(1, limit), 6),
        "binary_build_exp_yyyymmdd": MAX_BINARY_BUILD_EXP_YYYYMMDD,
        "binary_expired": bin_exp,
        "sponsors_url": SPONSORS_URL,
    }


def prometheus_metrics(today_yyyymmdd: int = 0) -> str:
    """Formats O(1) license, session quota, and SIMD ISA telemetry in standard OpenMetrics / Prometheus text format."""
    health = check_license_health(min_days_remaining=7, today_yyyymmdd=today_yyyymmdd)
    st = license_status(today_yyyymmdd=today_yyyymmdd)
    isa_code = 2 if st["isa"] == "AVX-512" else (1 if st["isa"] == "AVX2" else 0)
    ltag = st.get("license_tag", "TIER0-COMMUNITY")
    bmode = st.get("binding_mode", "community-tier0")
    htok = st.get("host_token", "")
    lines = [
        "# HELP silicium_license_slot_id Active Silicium license slot (0=Community Tier 0, 1..10=Enterprise).",
        "# TYPE silicium_license_slot_id gauge",
        f'silicium_license_slot_id{{engine="silicium-vector",license_tag="{ltag}",binding_mode="{bmode}",host_token="{htok}"}} {st["slot_id"]}',
        "# HELP silicium_license_max_vcpus Effective vCPU / Rayon thread cap unlocked.",
        "# TYPE silicium_license_max_vcpus gauge",
        f'silicium_license_max_vcpus{{engine="silicium-vector"}} {st["max_vcpus"]}',
        "# HELP silicium_license_expiry_yyyymmdd License expiration date in YYYYMMDD format (0 for Tier 0).",
        "# TYPE silicium_license_expiry_yyyymmdd gauge",
        f'silicium_license_expiry_yyyymmdd{{engine="silicium-vector"}} {st["exp_yyyymmdd"]}',
        "# HELP silicium_license_days_remaining Days remaining before license expiration.",
        "# TYPE silicium_license_days_remaining gauge",
        f'silicium_license_days_remaining{{engine="silicium-vector"}} {health["days_remaining"]}',
        "# HELP silicium_session_quota_used_bytes Bytes processed in the current 1-hour rolling window.",
        "# TYPE silicium_session_quota_used_bytes gauge",
        f'silicium_session_quota_used_bytes{{engine="silicium-vector"}} {st["session_bytes_used"]}',
        "# HELP silicium_session_quota_limit_bytes Hourly byte quota limit for Community Tier 0 (10 GiB).",
        "# TYPE silicium_session_quota_limit_bytes gauge",
        f'silicium_session_quota_limit_bytes{{engine="silicium-vector"}} {st["session_bytes_limit"]}',
        "# HELP silicium_simd_isa_level Active hardware SIMD ISA level (2=AVX-512, 1=AVX2, 0=Scalar).",
        "# TYPE silicium_simd_isa_level gauge",
        f'silicium_simd_isa_level{{engine="silicium-vector"}} {isa_code}',
    ]
    return "\n".join(lines) + "\n"


_OTEL_CACHE: Optional[Tuple[Tuple[int, str, str, str], int, Dict[str, Union[str, int, float, bool]]]] = None


def otel_span_attributes(today_yyyymmdd: int = 0) -> Dict[str, Union[str, int, float, bool]]:
    """Return a flat OpenTelemetry `Span.set_attributes(...)` dictionary (`< 1 us`, zero external dependency)."""
    global _OTEL_CACHE
    import time as _time

    now_ns = _time.monotonic_ns()
    cache_key = (
        int(today_yyyymmdd),
        os.environ.get("SILICIUM_ENTERPRISE_KEY", ""),
        os.environ.get("SILICIUM_ENTERPRISE_KEY_FILE", ""),
        host_token(),
    )
    if _OTEL_CACHE is not None and _OTEL_CACHE[0] == cache_key and (now_ns - _OTEL_CACHE[1]) < 1_000_000_000:
        return dict(_OTEL_CACHE[2])
    st = license_status(today_yyyymmdd=today_yyyymmdd)
    hl = check_license_health(min_days_remaining=1, today_yyyymmdd=today_yyyymmdd)
    slot_id = int(st["slot_id"])
    used = int(st["session_bytes_used"])
    limit = int(st["session_bytes_limit"])
    pct = 0.0 if slot_id > 0 or limit <= 0 else min(100.0, round((used / float(limit)) * 100.0, 4))
    res: Dict[str, Union[str, int, float, bool]] = {
        "silicium.engine": str(st["engine"]),
        "silicium.version": "1.0.0",
        "silicium.tier": str(st["tier"]),
        "silicium.slot_id": slot_id,
        "silicium.isa": str(st["isa"]),
        "silicium.license_tag": str(st.get("license_tag", "TIER0-COMMUNITY")),
        "silicium.binding_mode": str(st.get("binding_mode", "community-tier0")),
        "silicium.host_token": str(st.get("host_token", "")),
        "silicium.max_vcpus": int(st["max_vcpus"]),
        "silicium.vcpu.effective": int(st["max_vcpus"]),
        "silicium.vcpu.throttled": bool(st.get("is_cpu_throttled", False)),
        "silicium.session_bytes_used": used,
        "silicium.session.bytes_used": used,
        "silicium.session.bytes_limit": limit,
        "silicium.session.quota_pct": float(pct),
        "silicium.quota_utilization_pct": float(pct),
        "silicium.license.days_remaining": int(hl["days_remaining"]),
    }
    _OTEL_CACHE = (cache_key, now_ns, res)
    return dict(res)


def set_num_threads(num_threads: int) -> int:
    """Sets the user-requested Rayon thread pool cap (bounded by the active license slot)."""
    lib = _get_global_lib()
    fn = getattr(lib, "silicium_ann_set_num_threads_c", None)
    if fn is not None:
        fn.argtypes = [ctypes.c_size_t]
        fn.restype = ctypes.c_size_t
        return int(fn(max(0, int(num_threads))))
    return license_status()["max_vcpus"]


def compute_distance(va: np.ndarray, vb: np.ndarray, space: str = "l2") -> float:
    """Computes the exact SIMD distance between two 1D float32 vectors."""
    a = np.ascontiguousarray(va, dtype=np.float32).ravel()
    b = np.ascontiguousarray(vb, dtype=np.float32).ravel()
    if a.shape[0] != b.shape[0] or a.shape[0] == 0:
        raise ValueError("Vectors must be non-empty and have matching dimensions")
    sp = space.strip().lower()
    metric_code = 1 if sp in ("angular", "cosine", "cos") else (2 if sp in ("ip", "dot", "inner_product") else 0)
    lib = _get_global_lib()
    fn = getattr(lib, "silicium_ann_compute_distance_c", None)
    if fn is not None:
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_float),
        ]
        fn.restype = ctypes.c_int32
        out_d = ctypes.c_float(0.0)
        rc = fn(
            a.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            b.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            a.shape[0],
            metric_code,
            ctypes.byref(out_d),
        )
        if rc == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
            raise SiliciumQuotaExceededError()
        if rc == 0:
            return float(out_d.value)
    if metric_code == 0:
        diff = a - b
        return float(np.dot(diff, diff))
    if metric_code == 1:
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        return 1.0 - float(np.dot(a, b) / (na * nb)) if na > 1e-12 and nb > 1e-12 else 1.0
    return 1.0 - float(np.dot(a, b))


def cdist(XA: np.ndarray, XB: np.ndarray, space: str = "cosine") -> np.ndarray:
    """Computes the pairwise (M, N) float32 distance matrix between XA (M, D) and XB (N, D) using SIMD + Rayon."""
    a = np.ascontiguousarray(XA, dtype=np.float32)
    b = np.ascontiguousarray(XB, dtype=np.float32)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if b.ndim == 1:
        b = b.reshape(1, -1)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1] or a.shape[1] == 0:
        raise ValueError("XA and XB must be 2D float32 arrays with matching non-zero dimension D")
    m_rows, dim = int(a.shape[0]), int(a.shape[1])
    n_rows = int(b.shape[0])
    if m_rows == 0 or n_rows == 0:
        return np.empty((m_rows, n_rows), dtype=np.float32)
    sp = space.strip().lower()
    metric_code = 1 if sp in ("angular", "cosine", "cos") else (2 if sp in ("ip", "dot", "inner_product") else 0)
    out = np.empty((m_rows, n_rows), dtype=np.float32)
    lib = _get_global_lib()
    fn = getattr(lib, "silicium_ann_cdist_batch_c", None)
    if fn is not None:
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_float),
        ]
        fn.restype = ctypes.c_int32
        rc = fn(
            a.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            m_rows,
            b.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            n_rows,
            dim,
            metric_code,
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
        if rc == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
            raise SiliciumQuotaExceededError()
        if rc == 0:
            return out
    for i in range(m_rows):
        for j in range(n_rows):
            out[i, j] = compute_distance(a[i], b[j], space=space)
    return out


def hybrid_rrf(
    dense_ids: Union[np.ndarray, Sequence[int]],
    sparse_ids: Union[np.ndarray, Sequence[int]],
    k: int = 10,
    rrf_k: float = 60.0,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
    top_k: Optional[int] = None,
    alpha: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Fuses dense HNSW and sparse lexical (BM25) ID rankings via weighted Reciprocal Rank Fusion (RRF)."""
    d_arr = np.ascontiguousarray(dense_ids, dtype=np.int64).ravel()
    s_arr = np.ascontiguousarray(sparse_ids, dtype=np.int64).ravel()
    k_int = max(0, int(top_k if top_k is not None else k))
    if alpha is not None:
        dense_weight = float(alpha)
        sparse_weight = 1.0 - float(alpha)
    if k_int == 0 or (d_arr.size == 0 and s_arr.size == 0):
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
    out_ids = np.empty(k_int, dtype=np.int64)
    out_scores = np.empty(k_int, dtype=np.float32)
    out_count = ctypes.c_size_t(0)
    lib = _get_global_lib()
    fn = getattr(lib, "silicium_ann_hybrid_rrf_fuse_c", None)
    if fn is not None:
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_int64),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_int64),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        fn.restype = ctypes.c_int32
        d_ptr = d_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)) if d_arr.size > 0 else None
        s_ptr = s_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)) if s_arr.size > 0 else None
        rc = fn(
            d_ptr,
            d_arr.size,
            s_ptr,
            s_arr.size,
            k_int,
            float(rrf_k),
            float(dense_weight),
            float(sparse_weight),
            out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
            out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.byref(out_count),
        )
        if rc == 0:
            n_res = int(out_count.value)
            return out_ids[:n_res], out_scores[:n_res]
    scores: Dict[int, float] = {}
    eff_k = float(rrf_k) if rrf_k > 0 else 60.0
    for rank, did in enumerate(d_arr.tolist()):
        if did >= 0:
            scores[int(did)] = scores.get(int(did), 0.0) + float(dense_weight) / (eff_k + rank + 1.0)
    for rank, sid in enumerate(s_arr.tolist()):
        if sid >= 0:
            scores[int(sid)] = scores.get(int(sid), 0.0) + float(sparse_weight) / (eff_k + rank + 1.0)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k_int]
    return (
        np.array([kv[0] for kv in ranked], dtype=np.int64),
        np.array([kv[1] for kv in ranked], dtype=np.float32),
    )


def normalize_l2(vecs: np.ndarray, inplace: bool = True) -> np.ndarray:
    """Normalizes a 1D or 2D float32 array in-place (or on a copy when inplace=False) using SIMD + Rayon."""
    arr = vecs if (inplace and isinstance(vecs, np.ndarray) and vecs.dtype == np.float32 and vecs.flags["C_CONTIGUOUS"]) else np.array(vecs, dtype=np.float32, copy=True, order="C")
    if arr.ndim == 1:
        count, dim = 1, arr.shape[0]
    elif arr.ndim == 2:
        count, dim = arr.shape
    else:
        raise ValueError("Expected 1D or 2D float32 array")
    lib = _get_global_lib()
    fn = getattr(lib, "silicium_ann_normalize_l2_batch_c", None)
    if fn is not None and count > 0 and dim > 0:
        fn.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_size_t]
        fn.restype = ctypes.c_int32
        rc = int(fn(arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), count, dim))
        if rc == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
            raise SiliciumQuotaExceededError()
        return arr
    norms = np.linalg.norm(arr.reshape(count, dim), axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr.reshape(count, dim)[:] /= norms
    return arr


class SiliciumHNSW(BaseANN):
    def __init__(
        self,
        metric: str = "angular",
        method_param: Union[Dict[str, Any], int] = 24,
        efConstruction: int = 160,
        preset: str = "",
        M: Optional[int] = None,
        **kwargs: Any,
    ):
        self.metric = str(metric).strip().lower()
        if isinstance(method_param, dict):
            self.method_param = dict(method_param)
            self.method_param.update(kwargs)
            self.preset_name = str(self.method_param.get("preset", preset)).strip().lower()
            m_val = M if M is not None else self.method_param.get("M", 24)
            self.M = int(m_val)
            self.ef_construction = int(self.method_param.get("efConstruction", efConstruction))
        else:
            m_val = M if M is not None else kwargs.get("M", method_param)
            self.M = int(m_val)
            self.ef_construction = int(kwargs.get("efConstruction", efConstruction))
            self.preset_name = str(kwargs.get("preset", preset)).strip().lower()
            self.method_param = {"M": self.M, "efConstruction": self.ef_construction}
            if self.preset_name:
                self.method_param["preset"] = self.preset_name

        self.engine_ptr = None
        self.dim = 0
        self.count = 0
        self.ef = 24
        self._ood_calibrated = False
        self._ood_norm_ratio = 1.0
        self._ood_entry_neighbors: Optional[np.ndarray] = None
        self.variant_label = "Silicium"
        self.name = f"{self.variant_label}(M={self.M}, efConstruction={self.ef_construction}, ef={self.ef})"
        self.res: Optional[List[List[int]]] = None

        self.lib = _get_global_lib()

        self._fn_init = getattr(self.lib, "silicium_ann_init")
        self._fn_init.argtypes = [ctypes.c_size_t]
        self._fn_init.restype = ctypes.c_void_p

        self._fn_init_params = getattr(self.lib, "silicium_ann_init_params", None)
        if self._fn_init_params is not None:
            self._fn_init_params.argtypes = [ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t]
            self._fn_init_params.restype = ctypes.c_void_p

        self._fn_init_preset = getattr(self.lib, "silicium_ann_init_preset", None)
        if self._fn_init_preset is not None:
            self._fn_init_preset.argtypes = [ctypes.c_size_t, ctypes.c_uint32]
            self._fn_init_preset.restype = ctypes.c_void_p

        self._fn_set_ef = getattr(self.lib, "silicium_ann_set_ef_search", None)
        if self._fn_set_ef is not None:
            self._fn_set_ef.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            self._fn_set_ef.restype = None

        self._fn_set_kernel_mode = getattr(self.lib, "silicium_ann_set_kernel_mode", None)
        if self._fn_set_kernel_mode is not None:
            self._fn_set_kernel_mode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self._fn_set_kernel_mode.restype = None

        self._fn_set_metric = getattr(self.lib, "silicium_ann_set_metric", None)
        if self._fn_set_metric is not None:
            self._fn_set_metric.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self._fn_set_metric.restype = None

        self._fn_count = getattr(self.lib, "silicium_ann_count", None)
        if self._fn_count is not None:
            self._fn_count.argtypes = [ctypes.c_void_p]
            self._fn_count.restype = ctypes.c_size_t

        self._fn_dim = getattr(self.lib, "silicium_ann_dim", None)
        if self._fn_dim is not None:
            self._fn_dim.argtypes = [ctypes.c_void_p]
            self._fn_dim.restype = ctypes.c_size_t

        self._fn_get_vector = getattr(self.lib, "silicium_ann_get_vector_c", None)
        if self._fn_get_vector is not None:
            self._fn_get_vector.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_float)]
            self._fn_get_vector.restype = ctypes.c_int32

        self._fn_get_vectors_ptr = getattr(self.lib, "silicium_ann_get_vectors_ptr_c", None)
        if self._fn_get_vectors_ptr is not None:
            self._fn_get_vectors_ptr.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._fn_get_vectors_ptr.restype = ctypes.POINTER(ctypes.c_float)

        self._fn_stage_vectors = getattr(self.lib, "silicium_ann_stage_vectors_ptr_c", None)
        if self._fn_stage_vectors is not None:
            self._fn_stage_vectors.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            self._fn_stage_vectors.restype = ctypes.POINTER(ctypes.c_float)

        self._fn_commit_staged = getattr(self.lib, "silicium_ann_commit_staged_c", None)
        if self._fn_commit_staged is not None:
            self._fn_commit_staged.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
            self._fn_commit_staged.restype = ctypes.c_int32

        self._fn_save = getattr(self.lib, "silicium_ann_save_index", None)
        if self._fn_save is not None:
            self._fn_save.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            self._fn_save.restype = ctypes.c_int32

        self._fn_load = getattr(self.lib, "silicium_ann_load_index", None)
        if self._fn_load is not None:
            self._fn_load.argtypes = [ctypes.c_char_p]
            self._fn_load.restype = ctypes.c_void_p

        self._fn_add = getattr(self.lib, "silicium_ann_add")
        self._fn_add.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
        ]
        self._fn_add.restype = ctypes.c_int32

        self._fn_query = getattr(self.lib, "silicium_ann_query")
        self._fn_query.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_int32),
        ]
        self._fn_query.restype = ctypes.c_int32

        self._fn_query_batch = getattr(self.lib, "silicium_ann_query_batch", None)
        if self._fn_query_batch is not None:
            self._fn_query_batch.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
            ]
            self._fn_query_batch.restype = ctypes.c_int32

        self._fn_query_batch_single = getattr(self.lib, "silicium_ann_query_batch_single", None)
        if self._fn_query_batch_single is not None:
            self._fn_query_batch_single.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
            ]
            self._fn_query_batch_single.restype = ctypes.c_int32

        self._fn_query_with_distances = getattr(self.lib, "silicium_ann_query_with_distances", None)
        if self._fn_query_with_distances is not None:
            self._fn_query_with_distances.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
            ]
            self._fn_query_with_distances.restype = ctypes.c_int32

        self._fn_query_batch_with_distances = getattr(
            self.lib, "silicium_ann_query_batch_with_distances", None
        )
        if self._fn_query_batch_with_distances is not None:
            self._fn_query_batch_with_distances.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
            ]
            self._fn_query_batch_with_distances.restype = ctypes.c_int32

        self._fn_query_filtered = getattr(self.lib, "silicium_ann_query_filtered", None)
        if self._fn_query_filtered is not None:
            self._fn_query_filtered.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
            ]
            self._fn_query_filtered.restype = ctypes.c_int32

        self._fn_query_batch_filtered = getattr(self.lib, "silicium_ann_query_batch_filtered", None)
        if self._fn_query_batch_filtered is not None:
            self._fn_query_batch_filtered.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
            ]
            self._fn_query_batch_filtered.restype = ctypes.c_int32

        self._fn_reset_quota = getattr(self.lib, "silicium_ann_reset_session_quota", None)
        if self._fn_reset_quota is not None:
            self._fn_reset_quota.argtypes = []
            self._fn_reset_quota.restype = ctypes.c_int32

        self._fn_semantic_dedup = getattr(self.lib, "silicium_ann_semantic_dedup_c", None)
        if self._fn_semantic_dedup is not None:
            self._fn_semantic_dedup.argtypes = [
                ctypes.c_void_p,
                ctypes.c_float,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._fn_semantic_dedup.restype = ctypes.c_int32

        self._fn_query_range = getattr(self.lib, "silicium_ann_query_range_c", None)
        if self._fn_query_range is not None:
            self._fn_query_range.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_float,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._fn_query_range.restype = ctypes.c_int32

        self._fn_query_mmr = getattr(self.lib, "silicium_ann_query_mmr_c", None)
        if self._fn_query_mmr is not None:
            self._fn_query_mmr.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.c_float,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
            ]
            self._fn_query_mmr.restype = ctypes.c_int32

        self._fn_serialized_size = getattr(self.lib, "silicium_ann_serialized_size_c", None)
        if self._fn_serialized_size is not None:
            self._fn_serialized_size.argtypes = [ctypes.c_void_p]
            self._fn_serialized_size.restype = ctypes.c_size_t

        self._fn_save_to_bytes = getattr(self.lib, "silicium_ann_save_to_bytes_c", None)
        if self._fn_save_to_bytes is not None:
            self._fn_save_to_bytes.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._fn_save_to_bytes.restype = ctypes.c_int32

        self._fn_load_from_bytes = getattr(self.lib, "silicium_ann_load_from_bytes_c", None)
        if self._fn_load_from_bytes is not None:
            self._fn_load_from_bytes.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
            self._fn_load_from_bytes.restype = ctypes.c_void_p

        self._fn_free = getattr(self.lib, "silicium_ann_free")
        self._fn_free.argtypes = [ctypes.c_void_p]
        self._fn_free.restype = None

        self._query_buf = None
        self._query_ptr = None
        self._out_buf = np.empty(1024, dtype=np.int32)
        self._out_ptr = self._out_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
        self._dist_buf = np.empty(1024, dtype=np.float32)
        self._dist_ptr = self._dist_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

    @staticmethod
    def _check_rc(rc: Optional[int]) -> None:
        if rc == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
            raise SiliciumQuotaExceededError()

    def reset_session_quota(self) -> None:
        if self._fn_reset_quota is not None:
            self._fn_reset_quota()

    def _apply_metric(self) -> None:
        if self.engine_ptr and self._fn_set_metric is not None:
            if self.metric in ("angular", "cosine", "cos", "normalized"):
                metric_code = 1
            elif self.metric in ("dot", "dot_product", "dotproduct", "ip", "inner_product", "mips"):
                metric_code = 2
            else:
                metric_code = 0
            self._fn_set_metric(self.engine_ptr, metric_code)

    def _ensure_engine_initialized(self, dim: int) -> None:
        if self.engine_ptr is not None:
            return
        self.dim = int(dim)
        preset_map = {
            "fast_stream": 0,
            "faststream": 0,
            "fast": 0,
            "v1": 0,
            "balanced": 1,
            "pareto": 1,
            "high_fidelity": 2,
            "highfidelity": 2,
            "high": 2,
            "max": 2,
            "ultra_fidelity": 3,
            "ultrafidelity": 3,
            "ultra": 3,
        }
        if self._fn_init_params is not None and self.M > 0:
            self.engine_ptr = self._fn_init_params(self.dim, self.M, self.ef_construction)
        elif self.preset_name in preset_map and self._fn_init_preset is not None:
            self.engine_ptr = self._fn_init_preset(self.dim, preset_map[self.preset_name])
        else:
            self.engine_ptr = self._fn_init(self.dim)
        self._apply_metric()

    def add_incremental(self, X: np.ndarray) -> None:
        data = np.ascontiguousarray(X, dtype=np.float32)
        if data.ndim != 2:
            raise ValueError("Expected 2D float32 array")
        if not np.isfinite(data).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        n_rows, d = data.shape
        if n_rows == 0:
            return
        self._ensure_engine_initialized(d)
        data_p = data.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        rc = self._fn_add(self.engine_ptr, data_p, n_rows)
        self._check_rc(rc)
        self.count += n_rows

    def save(self, path: str) -> None:
        if not self.engine_ptr or self._fn_save is None:
            raise RuntimeError("Index is not initialized or save symbol is unavailable")
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        rc = self._fn_save(self.engine_ptr, str(path).encode("utf-8"))
        self._check_rc(rc)
        if rc != 0:
            raise IOError(f"Failed to save Silicium HNSW index to {path}")

    def load(self, path: str) -> None:
        if self._fn_load is None:
            raise RuntimeError("Load symbol is unavailable in native library")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Index file not found: {path}")
        loaded_ptr = self._fn_load(str(path).encode("utf-8"))
        if not loaded_ptr:
            try:
                with open(path, "rb") as fh:
                    hdr = fh.read(84)
                if len(hdr) >= 68 and hdr[:16] == b"SILICM_HNSW_V01\x00":
                    h_dim = int(struct.unpack_from("<Q", hdr, 16)[0])
                    h_cnt = int(struct.unpack_from("<Q", hdr, 60)[0])
                    st = license_status()
                    if int(st["slot_id"]) == 0:
                        if h_cnt > TIER0_MAX_INDEX_VECTORS:
                            raise SiliciumQuotaExceededError(
                                f"Silicium Community Tier 0 caps index size at {TIER0_MAX_INDEX_VECTORS} vectors (got {h_cnt}). Set SILICIUM_ENTERPRISE_KEY."
                            )
                        if int(st["session_bytes_used"]) + h_cnt * h_dim * 4 > int(st["session_bytes_limit"]):
                            raise SiliciumQuotaExceededError()
            except SiliciumQuotaExceededError:
                raise
            except Exception:
                pass
            raise IOError(f"Failed to deserialize Silicium HNSW index from {path}")
        if self.engine_ptr is not None:
            self._fn_free(self.engine_ptr)
        self.engine_ptr = loaded_ptr
        if self._fn_dim is not None and self._fn_count is not None:
            self.dim = int(self._fn_dim(self.engine_ptr))
            self.count = int(self._fn_count(self.engine_ptr))
        else:
            try:
                with open(path, "rb") as fh:
                    header = fh.read(84)
                if len(header) >= 68 and header[:16] == b"SILICM_HNSW_V01\x00":
                    self.dim = int(struct.unpack_from("<Q", header, 16)[0])
                    self.count = int(struct.unpack_from("<Q", header, 60)[0])
            except Exception:
                pass
        self.set_query_arguments(self.ef)

    def fit(self, X: np.ndarray) -> None:
        data = np.ascontiguousarray(X, dtype=np.float32)
        if not np.isfinite(data).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        if self.metric in ("angular", "cosine", "cos") or (
            self.metric == "normalized" and len(data) > 0 and abs(float(np.linalg.norm(data[0])) - 1.0) > 1e-3
        ):
            norms = np.linalg.norm(data, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            data = data / norms

        self.count, self.dim = data.shape

        use_cache = os.environ.get("SILICIUM_ENABLE_INDEX_CACHE", "0") == "1"
        cache_dir = os.environ.get("SILICIUM_INDEX_DIR", "cache")
        cache_file = os.path.join(
            cache_dir, f"hnsw_{self.count}x{self.dim}_m{self.M}_efc{self.ef_construction}_{self.metric}.bin"
        )

        if use_cache and os.path.exists(cache_file) and self._fn_load is not None:
            loaded_ptr = self._fn_load(cache_file.encode("utf-8"))
            if loaded_ptr:
                self.engine_ptr = loaded_ptr
                self._apply_metric()
                return

        if self.engine_ptr is not None:
            self._fn_free(self.engine_ptr)
            self.engine_ptr = None
        self._ensure_engine_initialized(self.dim)
        data_p = data.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        rc = self._fn_add(self.engine_ptr, data_p, self.count)
        self._check_rc(rc)

        if use_cache and self._fn_save is not None:
            os.makedirs(cache_dir, exist_ok=True)
            self._fn_save(self.engine_ptr, cache_file.encode("utf-8"))

    def fit_ood(self, X_train: np.ndarray, X_learn: np.ndarray, X_learn_neighbors: np.ndarray) -> None:
        if X_learn is not None and len(X_learn) > 0:
            sample_train = np.asarray(X_train[: min(len(X_train), 2048)], dtype=np.float32)
            sample_learn = np.asarray(X_learn[: min(len(X_learn), 2048)], dtype=np.float32)
            train_norm = float(np.mean(np.linalg.norm(sample_train, axis=1))) + 1e-9
            learn_norm = float(np.mean(np.linalg.norm(sample_learn, axis=1))) + 1e-9
            self._ood_norm_ratio = learn_norm / train_norm
        if X_learn_neighbors is not None and len(X_learn_neighbors) > 0:
            self._ood_entry_neighbors = np.asarray(X_learn_neighbors[: min(len(X_learn_neighbors), 64), 0], dtype=np.int32)
        self._ood_calibrated = True
        self.fit(X_train)

    def set_query_arguments(self, ef: int) -> None:
        self.ef = int(ef)
        self.name = f"{self.variant_label}(M={self.M}, efConstruction={self.ef_construction}, ef={self.ef})"
        if self.engine_ptr and self._fn_set_ef is not None:
            self._fn_set_ef(self.engine_ptr, self.ef)

    def query(
        self,
        v: np.ndarray,
        n: int = 10,
        return_distances: bool = False,
        filter_mask: Optional[np.ndarray] = None,
    ) -> Union[np.ndarray, tuple[np.ndarray, np.ndarray]]:
        if not np.isfinite(v).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        if isinstance(v, np.ndarray) and v.dtype == np.float32 and v.flags["C_CONTIGUOUS"]:
            q_ptr = v.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        else:
            if self._query_buf is None or len(self._query_buf) != self.dim:
                self._query_buf = np.empty(self.dim, dtype=np.float32)
                self._query_ptr = self._query_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            np.copyto(self._query_buf, v)
            q_ptr = self._query_ptr

        if n > len(self._out_buf):
            cap = max(n, len(self._out_buf) * 2)
            self._out_buf = np.empty(cap, dtype=np.int32)
            self._out_ptr = self._out_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
            self._dist_buf = np.empty(cap, dtype=np.float32)
            self._dist_ptr = self._dist_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        if filter_mask is not None and self._fn_query_filtered is not None:
            mask_u8 = np.ascontiguousarray(filter_mask, dtype=np.uint8).ravel()
            rc = self._fn_query_filtered(
                self.engine_ptr,
                q_ptr,
                n,
                mask_u8.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                mask_u8.shape[0],
                self._out_ptr,
                self._dist_ptr,
            )
            self._check_rc(rc)
            if n > 0 and int(self._out_buf[0]) == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
                raise SiliciumQuotaExceededError()
            if return_distances:
                return self._out_buf[:n].copy(), self._dist_buf[:n].copy()
            return self._out_buf[:n].copy()

        if return_distances and self._fn_query_with_distances is not None:
            rc = self._fn_query_with_distances(
                self.engine_ptr,
                q_ptr,
                n,
                self._out_ptr,
                self._dist_ptr,
            )
            self._check_rc(rc)
            if n > 0 and int(self._out_buf[0]) == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
                raise SiliciumQuotaExceededError()
            return self._out_buf[:n].copy(), self._dist_buf[:n].copy()

        rc = self._fn_query(
            self.engine_ptr,
            q_ptr,
            n,
            self._out_ptr,
        )
        self._check_rc(rc)
        if n > 0 and int(self._out_buf[0]) == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
            raise SiliciumQuotaExceededError()
        if return_distances:
            return self._out_buf[:n].copy(), np.zeros(n, dtype=np.float32)
        return self._out_buf[:n]

    def add_items(self, data: np.ndarray, ids: Optional[np.ndarray] = None) -> int:
        _ = ids
        return self.add_incremental(data)

    def knn_query(self, data: np.ndarray, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
        res = self.batch_query(data, n=int(k), return_distances=True)
        assert isinstance(res, tuple)
        return res

    def batch_query(
        self,
        X: np.ndarray,
        n: int = 10,
        return_distances: bool = False,
        filter_mask: Optional[np.ndarray] = None,
    ) -> Union[np.ndarray, tuple[np.ndarray, np.ndarray]]:
        queries = np.ascontiguousarray(X, dtype=np.float32)
        if not np.isfinite(queries).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        num_q = queries.shape[0]
        if num_q == 0:
            empty_ids = np.empty((0, int(n)), dtype=np.int32)
            self.res = empty_ids
            if return_distances:
                return empty_ids, np.empty((0, int(n)), dtype=np.float32)
            return empty_ids
        if filter_mask is not None and self._fn_query_batch_filtered is not None:
            mask_u8 = np.ascontiguousarray(filter_mask, dtype=np.uint8).ravel()
            out = np.empty((num_q, n), dtype=np.int32)
            dists = np.empty((num_q, n), dtype=np.float32)
            rc = self._fn_query_batch_filtered(
                self.engine_ptr,
                queries.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                num_q,
                n,
                mask_u8.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                mask_u8.shape[0],
                out.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                dists.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            )
            self._check_rc(rc)
            if num_q > 0 and n > 0 and int(out[0, 0]) == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
                raise SiliciumQuotaExceededError()
            self.res = out
            if return_distances:
                return out, dists
            return out

        if return_distances and self._fn_query_batch_with_distances is not None:
            out = np.empty((num_q, n), dtype=np.int32)
            dists = np.empty((num_q, n), dtype=np.float32)
            rc = self._fn_query_batch_with_distances(
                self.engine_ptr,
                queries.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                num_q,
                n,
                out.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                dists.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            )
            self._check_rc(rc)
            if num_q > 0 and n > 0 and int(out[0, 0]) == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
                raise SiliciumQuotaExceededError()
            self.res = out
            return out, dists

        force_single = os.environ.get("SILICIUM_BATCH_SINGLE", "0") == "1"
        if force_single and self._fn_query_batch_single is not None:
            batch_fn = self._fn_query_batch_single
        elif self._fn_query_batch is not None:
            batch_fn = self._fn_query_batch
        else:
            batch_fn = self._fn_query_batch_single

        if batch_fn is None:
            res_list = [self.query(q, n).copy() for q in X]
            self.res = np.array(res_list, dtype=np.int32)
            if return_distances:
                return self.res, np.zeros((num_q, n), dtype=np.float32)
            return self.res

        out = np.empty((num_q, n), dtype=np.int32)
        rc = batch_fn(
            self.engine_ptr,
            queries.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            num_q,
            n,
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        )
        self._check_rc(rc)
        if num_q > 0 and n > 0 and int(out[0, 0]) == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
            raise SiliciumQuotaExceededError()
        self.res = out
        if return_distances:
            return out, np.zeros((num_q, n), dtype=np.float32)
        return out

    def get_batch_results(self) -> Any:
        return self.res

    def get_additional(self) -> Dict[str, Any]:
        return {}

    def get_memory_usage(self) -> Optional[float]:
        try:
            import psutil

            proc = psutil.Process()
            try:
                return proc.memory_full_info().uss / 1024.0
            except Exception:
                return proc.memory_info().rss / 1024.0
        except Exception:
            return None

    def done(self) -> None:
        self.freeIndex()

    def freeIndex(self) -> None:
        if self.engine_ptr is not None:
            self._fn_free(self.engine_ptr)
            self.engine_ptr = None

    def __del__(self) -> None:
        self.freeIndex()

    def __str__(self) -> str:
        return self.name


class SiliciumQG(SiliciumHNSW):
    """Quantized Graph routing with exact FP32 top-pool reranking (VIBE scope)."""

    def __init__(
        self,
        metric: str,
        method_param: Union[Dict[str, Any], int] = 24,
        efConstruction: int = 160,
        preset: str = "balanced",
        M: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__(metric, method_param, efConstruction, preset, M=M, **kwargs)
        self.variant_label = "SiliciumQG"
        self.name = f"{self.variant_label}(M={self.M}, efConstruction={self.ef_construction}, ef={self.ef})"


Silicium = SiliciumHNSW
SiliciumVectorEngine = SiliciumHNSW


class Index:
    """High-level Zero-Copy Index wrapper for Silicium Vector with int64 external IDs, filter_mask, remove(), and Direct-to-Arena NDJSON ingestion."""

    def __init__(self, dim: int, space: str = "ip", m: int = 32, ef_construction: int = 200) -> None:
        self.dim = int(dim)
        self.space = str(space)
        self._engine = SiliciumVectorEngine(metric=space, method_param={"M": m, "efConstruction": ef_construction})
        self._fitted = False
        self._external_ids: List[int] = []
        self._id_to_nodes: Dict[int, List[int]] = {}
        self._deleted_mask: bytearray = bytearray()
        self._has_custom_ids: bool = False
        self._has_deletions: bool = False

    def __len__(self) -> int:
        if not self._fitted:
            return 0
        if self._has_deletions:
            return int(sum(self._deleted_mask))
        return int(self._engine.count)

    def _register_added_ids(self, n_added: int, ids: Optional[Union[np.ndarray, Sequence[int]]]) -> None:
        start_node = len(self._external_ids)
        if ids is not None:
            id_list = [int(x) for x in ids]
            if len(id_list) != n_added:
                raise ValueError(f"Expected {n_added} IDs, got {len(id_list)}")
            self._has_custom_ids = True
        else:
            id_list = list(range(start_node, start_node + n_added))
        for offset, ext_id in enumerate(id_list):
            node_idx = start_node + offset
            self._external_ids.append(ext_id)
            self._id_to_nodes.setdefault(ext_id, []).append(node_idx)
        self._deleted_mask.extend(b"\x01" * n_added)

    def add(self, vecs: np.ndarray, ids: Optional[Union[np.ndarray, Sequence[int]]] = None) -> None:
        arr = np.ascontiguousarray(vecs, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] != self.dim:
            raise ValueError(f"Expected (N, {self.dim}) float32 array")
        if not np.isfinite(arr).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        n_rows = int(arr.shape[0])
        if n_rows == 0:
            return
        self._engine.add_incremental(arr)
        self._register_added_ids(n_rows, ids)
        self._fitted = True

    def remove(self, ids: Union[np.ndarray, Sequence[int], int]) -> int:
        if isinstance(ids, (int, np.integer)):
            target_ids = [int(ids)]
        else:
            target_ids = [int(x) for x in ids]
        removed = 0
        for ext_id in target_ids:
            node_indices = self._id_to_nodes.get(ext_id, [])
            if not node_indices and 0 <= ext_id < len(self._deleted_mask) and not self._has_custom_ids:
                node_indices = [ext_id]
            for n_idx in node_indices:
                if 0 <= n_idx < len(self._deleted_mask) and self._deleted_mask[n_idx] != 0:
                    self._deleted_mask[n_idx] = 0
                    self._has_deletions = True
                    removed += 1
        return removed

    def get_vector(self, external_id: int) -> np.ndarray:
        if not self._fitted or self._engine.engine_ptr is None:
            raise RuntimeError("Index is empty")
        ext_id = int(external_id)
        node_indices = self._id_to_nodes.get(ext_id)
        node_idx = node_indices[-1] if node_indices else ext_id
        if node_idx < 0 or node_idx >= self._engine.count:
            raise KeyError(f"Vector ID {external_id} not found in index")
        out = np.empty(self.dim, dtype=np.float32)
        if self._engine._fn_get_vector is not None:
            rc = self._engine._fn_get_vector(
                self._engine.engine_ptr,
                node_idx,
                out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            )
            if rc == 0:
                return out
        raise RuntimeError("Failed to retrieve vector from native arena")

    def vectors(self) -> np.ndarray:
        if not self._fitted or self._engine.engine_ptr is None or self._engine._fn_get_vectors_ptr is None:
            return np.empty((0, self.dim), dtype=np.float32)
        c_cnt = ctypes.c_size_t(0)
        c_dim = ctypes.c_size_t(0)
        ptr = self._engine._fn_get_vectors_ptr(self._engine.engine_ptr, ctypes.byref(c_cnt), ctypes.byref(c_dim))
        if not ptr or c_cnt.value == 0 or c_dim.value == 0:
            return np.empty((0, self.dim), dtype=np.float32)
        return np.ctypeslib.as_array(ptr, shape=(int(c_cnt.value), int(c_dim.value)))

    def info(self) -> Dict[str, Any]:
        return {
            "dim": self.dim,
            "count": len(self),
            "raw_count": int(self._engine.count),
            "space": self.space,
            "m": int(self._engine.M),
            "ef_construction": int(self._engine.ef_construction),
            "ef_search": int(self._engine.ef),
        }

    def _encode_metadata_trailer(self) -> bytes:
        n_count = int(self._engine.count)
        space_norm = self.space.strip().lower()
        if space_norm in ("angular", "cosine", "cos", "normalized"):
            space_code = 1
        elif space_norm in ("dot", "dot_product", "dotproduct", "ip", "inner_product", "mips"):
            space_code = 2
        else:
            space_code = 0
        ext_arr = np.asarray(self._external_ids[:n_count], dtype="<i8")
        if ext_arr.shape[0] < n_count:
            ext_arr = np.arange(n_count, dtype="<i8")
        ext_bytes = ext_arr.tobytes()
        del_bytes = bytes(self._deleted_mask[:n_count])
        if len(del_bytes) < n_count:
            del_bytes = b"\x01" * n_count
        header = struct.pack(
            "<16sBBBHHxQ",
            b"SLCM_META_V0001\x00",
            int(self._has_custom_ids),
            int(self._has_deletions),
            space_code,
            min(65535, max(1, int(self._engine.M))),
            min(65535, max(1, int(self._engine.ef_construction))),
            n_count,
        )
        body = header + ext_bytes + del_bytes
        footer = struct.pack("<Q8s", len(body), b"SLCM_END")
        return body + footer

    def _restore_metadata_from_trailer(
        self,
        raw_bytes: Union[bytes, bytearray, memoryview],
        override_space: Optional[str] = None,
    ) -> None:
        mv = memoryview(raw_bytes)
        n_engine = int(self._engine.count)
        restored_space: Optional[str] = None
        if len(mv) >= 84 and bytes(mv[:16]) == b"SILICM_HNSW_V01\x00":
            h_dim, h_m, _h_m0, h_efc = struct.unpack_from("<QQQQ", mv, 16)
            h_metric = int(struct.unpack_from("<I", mv, 80)[0])
            if h_dim > 0:
                self.dim = int(h_dim)
                self._engine.dim = int(h_dim)
            if h_m > 0:
                self._engine.M = int(h_m)
                self._engine.method_param["M"] = int(h_m)
            if h_efc > 0:
                self._engine.ef_construction = int(h_efc)
                self._engine.method_param["efConstruction"] = int(h_efc)
            restored_space = {0: "l2", 1: "cosine", 2: "ip"}.get(h_metric, "l2")
            self._engine.name = (
                f"{self._engine.variant_label}(M={self._engine.M}, "
                f"efConstruction={self._engine.ef_construction}, ef={self._engine.ef})"
            )

        trailer_found = False
        if len(mv) >= 48 and bytes(mv[-8:]) == b"SLCM_END":
            body_len = int(struct.unpack_from("<Q", mv, len(mv) - 16)[0])
            start = len(mv) - 16 - body_len
            if start >= 0 and bytes(mv[start : start + 16]) == b"SLCM_META_V0001\x00":
                has_custom, has_del, space_code, t_m, t_efc, n_count = struct.unpack_from(
                    "<BBBHHxQ", mv, start + 16
                )
                if t_m > 0:
                    self._engine.M = int(t_m)
                    self._engine.method_param["M"] = int(t_m)
                if t_efc > 0:
                    self._engine.ef_construction = int(t_efc)
                    self._engine.method_param["efConstruction"] = int(t_efc)
                restored_space = {0: "l2", 1: "cosine", 2: "ip"}.get(int(space_code), restored_space or "l2")
                if n_count == n_engine and start + 32 + n_count * 9 <= len(mv) - 16:
                    ext_arr = np.frombuffer(mv, dtype="<i8", count=n_count, offset=start + 32)
                    del_slice = bytes(mv[start + 32 + n_count * 8 : start + 32 + n_count * 9])
                    self._external_ids = [int(x) for x in ext_arr]
                    self._id_to_nodes = {}
                    for idx, ext_id in enumerate(self._external_ids):
                        self._id_to_nodes.setdefault(ext_id, []).append(idx)
                    self._deleted_mask = bytearray(del_slice)
                    self._has_custom_ids = bool(has_custom)
                    self._has_deletions = bool(has_del)
                    trailer_found = True

        if not trailer_found:
            self._external_ids = list(range(n_engine))
            self._id_to_nodes = {i: [i] for i in range(n_engine)}
            self._deleted_mask = bytearray(b"\x01" * n_engine)
            self._has_custom_ids = False
            self._has_deletions = False

        if override_space is not None:
            eff_space = str(override_space).strip().lower()
            self.space = eff_space
            self._engine.metric = eff_space
            self._engine._apply_metric()
        elif restored_space is not None:
            self.space = restored_space
            self._engine.metric = restored_space
            self._engine._apply_metric()

    def save(self, path: str) -> None:
        if not self._fitted:
            raise RuntimeError("Index is empty; call add(vecs) before save(path)")
        self._engine.save(path)
        trailer = self._encode_metadata_trailer()
        with open(path, "ab") as fh:
            fh.write(trailer)

    def load(self, path: str, space: Optional[str] = None) -> None:
        self._engine.load(path)
        if self._engine.dim > 0:
            self.dim = self._engine.dim
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            self._restore_metadata_from_trailer(data, override_space=space)
        except Exception:
            self._restore_metadata_from_trailer(b"", override_space=space)
        self._fitted = True

    def to_bytes(self) -> bytes:
        if not self._fitted or self._engine.engine_ptr is None:
            raise RuntimeError("Index is empty; call add(vecs) before to_bytes()")
        fn_size = self._engine._fn_serialized_size
        fn_save_bytes = self._engine._fn_save_to_bytes
        if fn_size is not None and fn_save_bytes is not None:
            sz = int(fn_size(self._engine.engine_ptr))
            if sz <= 0:
                raise RuntimeError("Failed to compute serialized size of HnswIndex")
            buf = np.empty(sz, dtype=np.uint8)
            out_written = ctypes.c_size_t(0)
            rc = int(
                fn_save_bytes(
                    self._engine.engine_ptr,
                    buf.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                    sz,
                    ctypes.byref(out_written),
                )
            )
            if rc == ERR_COMMUNITY_SESSION_QUOTA_EXCEEDED:
                raise SiliciumQuotaExceededError()
            if rc < 0:
                raise RuntimeError("Failed to serialize HnswIndex into memory buffer")
            written = int(out_written.value)
            return buf[:written].tobytes() + self._encode_metadata_trailer()
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".slcm", delete=True) as tmp:
            self.save(tmp.name)
            tmp.seek(0)
            return tmp.read()

    @classmethod
    def from_bytes(
        cls,
        buffer: Union[bytes, bytearray, memoryview],
        space: Optional[str] = None,
    ) -> "Index":
        try:
            mv = buffer if isinstance(buffer, memoryview) else memoryview(buffer)
        except (BufferError, ValueError):
            mv = None
        if mv is None or not mv.contiguous:
            contig_u8 = np.ascontiguousarray(buffer).view(np.uint8).ravel()
            mv = memoryview(contig_u8)
        if len(mv) < 84:
            raise ValueError("Invalid or truncated SILICM_HNSW_V01 buffer")
        init_space = str(space) if space is not None else "ip"
        inst = cls(dim=1, space=init_space)
        fn_load_bytes = inst._engine._fn_load_from_bytes
        if fn_load_bytes is not None:
            arr = np.frombuffer(mv, dtype=np.uint8)
            loaded_ptr = fn_load_bytes(arr.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), len(arr))
            if not loaded_ptr:
                if bytes(mv[:16]) == b"SILICM_HNSW_V01\x00":
                    h_dim = int(struct.unpack_from("<Q", mv, 16)[0])
                    h_cnt = int(struct.unpack_from("<Q", mv, 60)[0])
                    st = license_status()
                    if int(st["slot_id"]) == 0:
                        if h_cnt > TIER0_MAX_INDEX_VECTORS:
                            raise SiliciumQuotaExceededError(
                                f"Silicium Community Tier 0 caps index size at {TIER0_MAX_INDEX_VECTORS} vectors (got {h_cnt}). Set SILICIUM_ENTERPRISE_KEY."
                            )
                        if int(st["session_bytes_used"]) + h_cnt * h_dim * 4 > int(st["session_bytes_limit"]):
                            raise SiliciumQuotaExceededError()
                raise ValueError("Failed to deserialize HnswIndex from memory buffer")
            if inst._engine.engine_ptr is not None:
                inst._engine._fn_free(inst._engine.engine_ptr)
            inst._engine.engine_ptr = loaded_ptr
            if inst._engine._fn_dim is not None and inst._engine._fn_count is not None:
                inst._engine.dim = int(inst._engine._fn_dim(loaded_ptr))
                inst._engine.count = int(inst._engine._fn_count(loaded_ptr))
            inst.dim = inst._engine.dim
            inst._restore_metadata_from_trailer(mv, override_space=space)
            inst._engine.set_query_arguments(inst._engine.ef)
            inst._fitted = True
            return inst
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".slcm", delete=True) as tmp:
            tmp.write(mv)
            tmp.flush()
            inst.load(tmp.name, space=space)
            return inst

    @classmethod
    def from_file(cls, path: str, space: Optional[str] = None) -> "Index":
        init_space = str(space) if space is not None else "ip"
        inst = cls(dim=1, space=init_space)
        inst.load(path, space=space)
        return inst

    @classmethod
    def from_ndjson(
        cls,
        payload: Union[bytes, bytearray, memoryview, str],
        dim: int = 0,
        vector_key: str = "embedding",
        id_key: Optional[str] = "id",
        space: str = "ip",
        m: int = 32,
        ef_construction: int = 200,
    ) -> "Index":
        """Direct-to-Arena Zero-Copy ingestion from NDJSON (.jsonl) via silicium_json."""
        import silicium_json

        if dim <= 0:
            rows, detected_dim = silicium_json.ndjson_inspect(payload, vector_key=vector_key)
            dim = detected_dim
        else:
            rows, _ = silicium_json.ndjson_inspect(payload, vector_key=vector_key)
        if rows <= 0 or dim <= 0:
            raise ValueError("NDJSON payload contains no valid vectors")

        inst = cls(dim=dim, space=space, m=m, ef_construction=ef_construction)
        inst._engine._ensure_engine_initialized(dim)
        normalize_flag = space.strip().lower() in ("angular", "cosine", "cos")

        if inst._engine._fn_stage_vectors is not None and inst._engine._fn_commit_staged is not None:
            stage_ptr = inst._engine._fn_stage_vectors(inst._engine.engine_ptr, rows)
            if not stage_ptr:
                st = license_status()
                if int(st["slot_id"]) == 0 and rows > TIER0_MAX_INDEX_VECTORS:
                    raise SiliciumQuotaExceededError(
                        f"Silicium Community Tier 0 caps index size at {TIER0_MAX_INDEX_VECTORS} vectors (got {rows}). Set SILICIUM_ENTERPRISE_KEY."
                    )
                raise RuntimeError("Failed to stage vectors in native HnswIndex arena")
            ids_arr = np.empty(rows, dtype=np.int64)
            decoded_rows = silicium_json.extract_ndjson_f32_into(
                payload,
                stage_ptr,
                rows,
                dim,
                vector_key=vector_key,
                id_key=id_key,
                out_ids=ids_arr,
                normalize_l2=normalize_flag,
            )
            rc = inst._engine._fn_commit_staged(inst._engine.engine_ptr, decoded_rows, 1)
            inst._engine._check_rc(rc)
            inst._engine.count += decoded_rows
            inst._register_added_ids(decoded_rows, ids_arr[:decoded_rows] if id_key else None)
            inst._fitted = True
            return inst

        mat, ids_arr = silicium_json.extract_ndjson_f32(
            payload, dim=dim, vector_key=vector_key, id_key=id_key, normalize_l2=normalize_flag
        )
        inst.add(mat, ids=ids_arr if id_key else None)
        return inst

    def _build_effective_mask(self, filter_mask: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if filter_mask is None and not self._has_deletions:
            return None
        n_total = self._engine.count
        eff = np.frombuffer(self._deleted_mask, dtype=np.uint8, count=n_total).copy()
        if filter_mask is not None:
            fm = np.asarray(filter_mask, dtype=np.uint8).ravel()
            m_len = min(n_total, fm.shape[0])
            eff[:m_len] &= (fm[:m_len] != 0).astype(np.uint8)
            if m_len < n_total:
                eff[m_len:] = 0
        return eff

    def _map_internal_ids(self, raw_ids: np.ndarray) -> np.ndarray:
        if not self._has_custom_ids:
            return raw_ids
        id_lut = np.asarray(self._external_ids, dtype=np.int64)
        flat = raw_ids.ravel()
        mapped = np.where((flat >= 0) & (flat < len(id_lut)), id_lut[np.clip(flat, 0, max(0, len(id_lut) - 1))], -1)
        return mapped.reshape(raw_ids.shape)

    def deduplicate_semantic(
        self,
        cosine_threshold: float = 0.95,
        prefer_lowest_id: bool = True,
    ) -> Tuple[np.ndarray, int]:
        """Identify near-duplicate vectors in the HNSW arena and return (keep_mask_uint8, removed_count)."""
        if not self._fitted or self._engine.engine_ptr is None:
            return np.empty(0, dtype=np.uint8), 0
        n_total = int(self._engine.count)
        keep_mask = np.ones(n_total, dtype=np.uint8)
        fn_dedup = self._engine._fn_semantic_dedup
        if fn_dedup is None:
            raise RuntimeError("silicium_ann_semantic_dedup_c symbol is unavailable in native library")
        kept_cnt = ctypes.c_size_t(0)
        dist_thresh = (
            max(0.0, float((2.0 * max(0.0, 1.0 - float(cosine_threshold))) ** 0.5))
            if self.space in ("l2", "euclidean")
            else max(0.0, 1.0 - float(cosine_threshold))
        )
        rc = int(
            fn_dedup(
                self._engine.engine_ptr,
                ctypes.c_float(dist_thresh),
                ctypes.c_uint32(1 if prefer_lowest_id else 0),
                keep_mask.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                ctypes.byref(kept_cnt),
            )
        )
        self._engine._check_rc(rc)
        if rc < 0:
            raise RuntimeError(f"silicium_ann_semantic_dedup_c failed with status {rc}")
        if self._has_deletions:
            for idx in range(n_total):
                if self._deleted_mask[idx] == 0:
                    keep_mask[idx] = 0
        removed = int(n_total - np.count_nonzero(keep_mask))
        return keep_mask, removed

    def search_range(
        self,
        query: np.ndarray,
        radius: float = 0.05,
        max_results: int = 256,
        filter_mask: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return all neighbors within distance threshold `radius` as (ids_int64, distances_float32)."""
        if not self._fitted or self._engine.engine_ptr is None:
            raise RuntimeError("Index is empty; call add(vecs) or load(path) first")
        q_arr = np.ascontiguousarray(query, dtype=np.float32).ravel()
        if q_arr.shape[0] != self.dim:
            raise ValueError(f"Expected query of dimension {self.dim}, got {q_arr.shape[0]}")
        cap = max(1, int(max_results))
        eff_mask = self._build_effective_mask(filter_mask)
        mask_ptr = (
            eff_mask.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
            if eff_mask is not None
            else ctypes.cast(0, ctypes.POINTER(ctypes.c_uint8))
        )
        mask_len = int(eff_mask.shape[0]) if eff_mask is not None else 0
        raw_ids = np.empty(cap, dtype=np.int32)
        dists = np.empty(cap, dtype=np.float32)
        fn_range = self._engine._fn_query_range
        if fn_range is None:
            raise RuntimeError("silicium_ann_query_range_c symbol is unavailable in native library")
        out_cnt = ctypes.c_size_t(0)
        rc = int(
            fn_range(
                self._engine.engine_ptr,
                q_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_float(float(radius)),
                cap,
                mask_ptr,
                mask_len,
                raw_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                dists.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.byref(out_cnt),
            )
        )
        self._engine._check_rc(rc)
        if rc < 0:
            raise RuntimeError(f"silicium_ann_query_range_c failed with status {rc}")
        count = int(out_cnt.value)
        mapped = np.asarray(self._map_internal_ids(raw_ids[:count]), dtype=np.int64)
        return mapped, dists[:count].copy()

    def search_mmr(
        self,
        query: np.ndarray,
        k: int = 10,
        fetch_k: int = 50,
        lambda_mult: float = 0.5,
        filter_mask: Optional[np.ndarray] = None,
        return_distances: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """Maximal Marginal Relevance (MMR) diversified top-k retrieval executed natively in Rust."""
        if not self._fitted or self._engine.engine_ptr is None:
            raise RuntimeError("Index is empty; call add(vecs) or load(path) first")
        q_arr = np.ascontiguousarray(query, dtype=np.float32).ravel()
        if q_arr.shape[0] != self.dim:
            raise ValueError(f"Expected query of dimension {self.dim}, got {q_arr.shape[0]}")
        k_int = max(1, int(k))
        fk_int = max(k_int, int(fetch_k))
        eff_mask = self._build_effective_mask(filter_mask)
        mask_ptr = (
            eff_mask.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
            if eff_mask is not None
            else ctypes.cast(0, ctypes.POINTER(ctypes.c_uint8))
        )
        mask_len = int(eff_mask.shape[0]) if eff_mask is not None else 0
        raw_ids = np.full(k_int, -1, dtype=np.int32)
        dists = np.zeros(k_int, dtype=np.float32)
        fn_mmr = self._engine._fn_query_mmr
        if fn_mmr is None:
            raise RuntimeError("silicium_ann_query_mmr_c symbol is unavailable in native library")
        rc = int(
            fn_mmr(
                self._engine.engine_ptr,
                q_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                k_int,
                fk_int,
                ctypes.c_float(float(lambda_mult)),
                mask_ptr,
                mask_len,
                raw_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                dists.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            )
        )
        self._engine._check_rc(rc)
        if rc < 0:
            raise RuntimeError(f"silicium_ann_query_mmr_c failed with status {rc}")
        mapped = self._map_internal_ids(raw_ids)
        if return_distances:
            return mapped, dists
        return mapped

    def search(
        self,
        queries: np.ndarray,
        k: int = 10,
        ef: int = 64,
        return_distances: bool = False,
        filter_mask: Optional[np.ndarray] = None,
    ) -> Union[np.ndarray, tuple[np.ndarray, np.ndarray]]:
        arr = np.ascontiguousarray(queries, dtype=np.float32)
        if arr.ndim == 1:
            if arr.shape[0] != self.dim:
                raise ValueError(f"Expected query of dimension {self.dim}, got {arr.shape[0]}")
        elif arr.ndim == 2:
            if arr.shape[1] != self.dim:
                raise ValueError(f"Expected queries of dimension (N, {self.dim}), got {arr.shape}")
        else:
            raise ValueError(f"Expected 1D or 2D float32 query array, got {arr.ndim}D")
        if not np.isfinite(arr).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        k_int = max(0, int(k))
        if not self._fitted or len(self) == 0 or (arr.ndim == 2 and arr.shape[0] == 0):
            return np.empty((0, k_int), dtype=np.int64), np.empty((0, k_int), dtype=np.float32)
        self._engine.set_query_arguments(ef)
        eff_mask = self._build_effective_mask(filter_mask)
        if arr.ndim == 1:
            res = self._engine.query(arr, k_int, return_distances=return_distances, filter_mask=eff_mask)
        else:
            res = self._engine.batch_query(arr, k_int, return_distances=return_distances, filter_mask=eff_mask)
        if return_distances:
            ids_out, dists_out = res  # type: ignore[misc]
            return self._map_internal_ids(ids_out), dists_out
        return self._map_internal_ids(res)  # type: ignore[arg-type]

    def search_json(
        self,
        queries: np.ndarray,
        k: int = 10,
        ef: int = 64,
        include_distances: bool = True,
        filter_mask: Optional[np.ndarray] = None,
    ) -> bytes:
        ids_out, dists_out = self.search(
            queries, k=k, ef=ef, return_distances=True, filter_mask=filter_mask
        )
        import silicium_json

        return silicium_json.format_search_results(
            np.asarray(ids_out, dtype=np.int64).ravel(),
            np.asarray(dists_out, dtype=np.float32).ravel(),
            include_distances=include_distances,
        )


def align_up_64b(n: int) -> int:
    val = int(n)
    if val <= 0:
        return max(0, val)
    return max(val, (val + 63) & ~63)


def ingest_ndjson_to_vector_arena_zero_copy(
    ndjson_payload: Union[bytes, bytearray, memoryview, str],
    dim: int = 0,
    vector_key: str = "embedding",
    id_key: Optional[str] = "id",
    space: str = "ip",
    m: int = 32,
    ef_construction: int = 200,
    check_pii: bool = True,
    max_tokens: int = 262144,
    embedding_key: Optional[str] = None,
    text_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Zero-Copy C-ABI RAG bridge from NDJSON to 64B-aligned Silicium Vector Arena."""
    import importlib.util
    import time
    from pathlib import Path

    t0 = time.perf_counter()
    eff_vec_key = str(embedding_key) if embedding_key is not None else str(vector_key)
    sys.modules.setdefault("silicium_vector", sys.modules[__name__])
    mod_json = sys.modules.get("silicium_json")
    if mod_json is None:
        try:
            import silicium_json as mod_json  # type: ignore[no-redef]
        except ImportError:
            cands = sorted(Path(__file__).resolve().parents[3].glob("*json*/sas_export/payload/module.py"))
            if not cands:
                raise RuntimeError("silicium_json module is unavailable")
            spec_j = importlib.util.spec_from_file_location("silicium_json", cands[0])
            if spec_j is None or spec_j.loader is None:
                raise RuntimeError("silicium_json module is unavailable")
            mod_json = importlib.util.module_from_spec(spec_j)
            sys.modules["silicium_json"] = mod_json
            spec_j.loader.exec_module(mod_json)

    llm_info = mod_json.inspect_llm_request(ndjson_payload, max_tokens=max_tokens, check_pii=check_pii)
    rows, detected_dim = mod_json.ndjson_inspect(ndjson_payload, vector_key=eff_vec_key)
    eff_dim = int(dim) if int(dim) > 0 else int(detected_dim)
    if rows <= 0 or eff_dim <= 0:
        raise ValueError("NDJSON payload contains no valid vectors")
    idx = Index.from_ndjson(
        ndjson_payload,
        dim=eff_dim,
        vector_key=eff_vec_key,
        id_key=id_key,
        space=space,
        m=m,
        ef_construction=ef_construction,
    )
    texts: list[str] = []
    if text_key is not None:
        try:
            texts, _ = mod_json.filter_ndjson_texts(
                ndjson_payload, text_key=str(text_key), score_key="", min_score=-1e30, id_key=id_key
            )
            if not texts:
                raw_b = ndjson_payload.encode("utf-8") if isinstance(ndjson_payload, str) else bytes(ndjson_payload)
                for ln in raw_b.splitlines():
                    if ln.strip():
                        tv = mod_json.get_field_str(ln, str(text_key))
                        if tv is not None:
                            texts.append(tv)
        except Exception:
            texts = []
    ingested_rows = int(len(idx))
    return {
        "index": idx,
        "texts": texts,
        "rows_ingested": ingested_rows,
        "dim": eff_dim,
        "aligned_arena_bytes_64b": align_up_64b(ingested_rows * eff_dim * 4),
        "arena_alignment_bytes": 64,
        "already_billed_quota": 1,
        "pii_flags": int(llm_info.get("pii_flags", 0)),
        "estimated_tokens": int(llm_info.get("estimated_tokens", 0)),
        "zero_python_heap_objects": True,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 3),
    }


class SiliciumVectorStore:
    """1-line drop-in VectorStore compatible with LangChain and LlamaIndex backed by 64B-aligned Silicium Vector Arena."""

    def __init__(
        self,
        dim: int = 1536,
        space: str = "ip",
        m: int = 32,
        ef_construction: int = 200,
        index: Optional[Index] = None,
        texts: Optional[Dict[int, str]] = None,
        metadatas: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> None:
        if index is not None:
            self.index = index
            self.dim = int(index.dim)
            self.space = str(index.space)
        else:
            self.dim = int(dim)
            self.space = str(space)
            self.index = Index(dim=self.dim, space=self.space, m=m, ef_construction=ef_construction)
        self._texts: Dict[int, str] = dict(texts) if texts is not None else {}
        self._metadatas: Dict[int, Dict[str, Any]] = dict(metadatas) if metadatas is not None else {}
        self.last_bridge_telemetry: Dict[str, Any] = {}

    def __len__(self) -> int:
        return len(self.index)

    @classmethod
    def from_ndjson(
        cls,
        ndjson_payload: Union[bytes, bytearray, memoryview, str],
        dim: int = 0,
        vector_key: str = "embedding",
        id_key: Optional[str] = "id",
        text_key: Optional[str] = None,
        space: str = "ip",
        m: int = 32,
        ef_construction: int = 200,
    ) -> "SiliciumVectorStore":
        bridge_res = ingest_ndjson_to_vector_arena_zero_copy(
            ndjson_payload,
            dim=dim,
            vector_key=vector_key,
            id_key=id_key,
            space=space,
            m=m,
            ef_construction=ef_construction,
        )
        idx: Index = bridge_res["index"]
        texts_map: Dict[int, str] = {}
        if text_key is not None:
            import silicium_json

            extracted_texts, extracted_ids = silicium_json.filter_ndjson_texts(
                ndjson_payload,
                text_key=text_key,
                score_key="meta.score",
                min_score=-1e30,
                id_key=id_key,
                unescape=True,
            )
            for txt, doc_id in zip(extracted_texts, extracted_ids):
                texts_map[int(doc_id)] = str(txt)
        store = cls(
            dim=int(bridge_res["dim"]),
            space=space,
            m=m,
            ef_construction=ef_construction,
            index=idx,
            texts=texts_map,
        )
        store.last_bridge_telemetry = bridge_res
        return store

    def add_vectors(
        self,
        vectors: np.ndarray,
        ids: Optional[Sequence[int]] = None,
        texts: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[int]:
        arr = np.ascontiguousarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        n_rows = int(arr.shape[0])
        base_id = len(self.index)
        eff_ids = [int(x) for x in ids] if ids is not None else [base_id + i for i in range(n_rows)]
        self.index.add(arr, ids=eff_ids)
        if texts is not None:
            for doc_id, txt in zip(eff_ids, texts):
                self._texts[int(doc_id)] = str(txt)
        if metadatas is not None:
            for doc_id, meta in zip(eff_ids, metadatas):
                self._metadatas[int(doc_id)] = dict(meta)
        return eff_ids

    def similarity_search_with_score_by_vector(
        self,
        embedding: Union[np.ndarray, Sequence[float]],
        k: int = 4,
        ef: int = 64,
        filter_mask: Optional[np.ndarray] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        q = np.ascontiguousarray(embedding, dtype=np.float32).ravel()
        if q.shape[0] != self.dim:
            raise ValueError(f"Expected embedding of dimension {self.dim}, got {q.shape[0]}")
        if not np.isfinite(q).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        if len(self.index) == 0:
            return []
        eff_k = max(1, min(int(k), max(1, len(self.index))))
        ids_out, dists_out = self.index.search(
            q, k=eff_k, ef=ef, return_distances=True, filter_mask=filter_mask
        )
        ids_flat = np.asarray(ids_out, dtype=np.int64).ravel()
        dists_flat = np.asarray(dists_out, dtype=np.float32).ravel()
        results: List[Tuple[Dict[str, Any], float]] = []
        for doc_id_val, dist_val in zip(ids_flat, dists_flat):
            doc_id = int(doc_id_val)
            if doc_id < 0:
                continue
            txt = self._texts.get(doc_id, "")
            meta = dict(self._metadatas.get(doc_id, {}))
            meta.setdefault("id", doc_id)
            doc = {"id": doc_id, "page_content": txt, "text": txt, "metadata": meta}
            results.append((doc, float(dist_val)))
        return results

    def similarity_search_by_vector(
        self,
        embedding: Union[np.ndarray, Sequence[float]],
        k: int = 4,
        ef: int = 64,
        filter_mask: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        scored = self.similarity_search_with_score_by_vector(
            embedding, k=k, ef=ef, filter_mask=filter_mask
        )
        return [doc for doc, _score in scored]

    def query(
        self,
        query_embedding: Union[np.ndarray, Sequence[float]],
        similarity_top_k: int = 4,
        ef: int = 64,
    ) -> Dict[str, Any]:
        scored = self.similarity_search_with_score_by_vector(
            query_embedding, k=similarity_top_k, ef=ef
        )
        return {
            "nodes": [doc for doc, _score in scored],
            "ids": [int(doc["id"]) for doc, _score in scored],
            "similarities": [float(score) for _doc, score in scored],
        }


class SiliciumSemanticCache:
    """1-line drop-in semantic & prompt cache compatible with LiteLLM CustomCache and LangChain BaseCache."""

    def __init__(
        self,
        dim: int = 8,
        space: str = "l2",
        distance_threshold: float = 0.15,
        m: int = 16,
        ef_construction: int = 64,
    ) -> None:
        self.dim = max(1, int(dim))
        self.space = str(space)
        self.distance_threshold = float(distance_threshold)
        self.index = Index(dim=self.dim, space=self.space, m=m, ef_construction=ef_construction)
        self._entries: Dict[int, Any] = {}
        self._prompts: Dict[int, str] = {}
        self._exact_map: Dict[str, Any] = {}
        self._next_id: int = 0

    def _to_embedding(self, key_or_embedding: Union[np.ndarray, Sequence[float], str]) -> np.ndarray:
        if isinstance(key_or_embedding, str):
            digest = hashlib.blake2b(key_or_embedding.encode("utf-8"), digest_size=64).digest()
            raw_u8 = np.frombuffer(digest, dtype=np.uint8).astype(np.float32)
            reps = (self.dim + len(raw_u8) - 1) // len(raw_u8)
            vec = np.tile(raw_u8, reps)[: self.dim] - 127.5
            norm = float(np.linalg.norm(vec))
            if norm > 0.0:
                vec = vec / norm
            return np.ascontiguousarray(vec, dtype=np.float32)
        arr = np.ascontiguousarray(key_or_embedding, dtype=np.float32).ravel()
        if arr.shape[0] != self.dim:
            raise ValueError(f"Expected embedding of dimension {self.dim}, got {arr.shape[0]}")
        if not np.isfinite(arr).all():
            raise ValueError("Input vectors must be finite (NaN or Inf detected)")
        return arr

    def set_cache(
        self,
        key_or_embedding: Union[np.ndarray, Sequence[float], str],
        value: Any,
        prompt: str = "",
    ) -> int:
        if not isinstance(prompt, str):
            vec = self._to_embedding(prompt).reshape(1, self.dim)
            prompt_str = str(key_or_embedding) if isinstance(key_or_embedding, str) else ""
        else:
            vec = self._to_embedding(key_or_embedding).reshape(1, self.dim)
            prompt_str = prompt or (key_or_embedding if isinstance(key_or_embedding, str) else "")
        if isinstance(key_or_embedding, str):
            self._exact_map[key_or_embedding] = value
        entry_id = self._next_id
        self._next_id += 1
        self.index.add(vec, ids=[entry_id])
        self._entries[entry_id] = value
        self._prompts[entry_id] = prompt_str
        return entry_id

    def get_cache(
        self,
        key_or_embedding: Union[np.ndarray, Sequence[float], str],
        distance_threshold: Optional[float] = None,
    ) -> Any:
        if isinstance(key_or_embedding, str) and key_or_embedding in self._exact_map:
            return self._exact_map[key_or_embedding]
        if len(self.index) == 0:
            return None
        thresh = float(self.distance_threshold if distance_threshold is None else distance_threshold)
        vec = self._to_embedding(key_or_embedding)
        ids_out, dists_out = self.index.search(vec, k=1, ef=32, return_distances=True)
        ids_flat = np.asarray(ids_out, dtype=np.int64).ravel()
        dists_flat = np.asarray(dists_out, dtype=np.float32).ravel()
        if len(ids_flat) == 0:
            return None
        best_id = int(ids_flat[0])
        best_dist = float(dists_flat[0])
        if best_id >= 0 and best_dist <= thresh:
            return self._entries.get(best_id)
        return None

    def async_set_cache(
        self,
        key_or_embedding: Union[np.ndarray, Sequence[float], str],
        value: Any,
        prompt: str = "",
    ) -> int:
        return self.set_cache(key_or_embedding, value, prompt=prompt)

    def async_get_cache(
        self,
        key_or_embedding: Union[np.ndarray, Sequence[float], str],
        distance_threshold: Optional[float] = None,
    ) -> Any:
        return self.get_cache(key_or_embedding, distance_threshold=distance_threshold)

    def update(
        self,
        prompt: str,
        llm_string: str,
        return_val: Any,
        embedding: Optional[Union[np.ndarray, Sequence[float]]] = None,
    ) -> int:
        key = embedding if embedding is not None else f"{llm_string}::{prompt}"
        return self.set_cache(key, return_val, prompt=prompt)

    def lookup(
        self,
        prompt: str,
        llm_string: str,
        embedding: Optional[Union[np.ndarray, Sequence[float]]] = None,
    ) -> Any:
        key = embedding if embedding is not None else f"{llm_string}::{prompt}"
        return self.get_cache(key)


def _load_peer_json_module() -> Any:
    import importlib.util
    from pathlib import Path

    self_mod = sys.modules.get(__name__)
    if self_mod is not None:
        sys.modules.setdefault("silicium_vector", self_mod)
    mod_json = sys.modules.get("silicium_json")
    if mod_json is not None:
        return mod_json
    try:
        import silicium_json as mod_json  # type: ignore[no-redef]

        return mod_json
    except ImportError:
        here = Path(__file__).resolve()
        cands: list[Path] = []
        for parent_idx in (3, 2, 1):
            if len(here.parents) > parent_idx:
                base_p = here.parents[parent_idx]
                cands.extend(sorted(base_p.glob("*json*/sas_export/payload/module.py")))
                cands.extend(sorted(base_p.glob("*json*/module.py")))
        if not cands:
            raise RuntimeError("silicium_json module is unavailable")
        spec_j = importlib.util.spec_from_file_location("silicium_json", cands[0])
        if spec_j is None or spec_j.loader is None:
            raise RuntimeError("silicium_json module is unavailable")
        mod_json = importlib.util.module_from_spec(spec_j)
        sys.modules["silicium_json"] = mod_json
        spec_j.loader.exec_module(mod_json)
        return mod_json


class SiliciumLangfuseTracer:
    """OpenTelemetry GenAI & Langfuse span enricher (`SAO-GATEWAY-LITELLM-001`)."""

    def __init__(
        self,
        residency_zone: str = "on-prem-sovereign",
        actor_id: str = "litellm-proxy",
        default_model: str = "gpt-4o-mini",
        redact_pii: bool = False,
    ) -> None:
        self._delegate: Any = None
        self.residency_zone = str(residency_zone)
        self.actor_id = str(actor_id)
        self.default_model = str(default_model)
        self.redact_pii = bool(redact_pii)

    def _get_delegate(self) -> Any:
        if self._delegate is None:
            mod_json = _load_peer_json_module()
            self._delegate = mod_json.SiliciumLangfuseTracer(
                residency_zone=self.residency_zone,
                actor_id=self.actor_id,
                default_model=self.default_model,
                redact_pii=self.redact_pii,
            )
        return self._delegate

    def scrub_payload(self, request_payload: Any) -> Dict[str, Any]:
        return dict(self._get_delegate().scrub_payload(request_payload))

    def enrich_langfuse_span(
        self,
        request_payload: Any,
        response_obj: Any = None,
        cache_hit: bool = False,
        actor_id: str = "litellm-proxy",
        ai_model: str = "gpt-4o-mini",
    ) -> Dict[str, Any]:
        return dict(
            self._get_delegate().enrich_langfuse_span(
                request_payload,
                response_obj=response_obj,
                cache_hit=cache_hit,
                actor_id=actor_id,
                ai_model=ai_model,
            )
        )


def _resolve_litellm_custom_logger_base() -> type:
    try:
        from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]

        if isinstance(CustomLogger, type):
            return CustomLogger
    except Exception:
        pass
    return object


class SiliciumLiteLLMGateway(_resolve_litellm_custom_logger_base()):  # type: ignore[misc]
    """1-Click LiteLLM Proxy (`v1.108+` CustomLogger 4-arg & 1-arg bimodal) & Kong AI Gateway Callback (`SAO-GATEWAY-LITELLM-001` / `SAO-GATEWAY-LITELLM-V1108`)."""

    def __init__(
        self,
        num_workers: int = 8,
        max_tokens: int = 262144,
        pii_policy: str = "block",
        enable_semantic_cache: bool = True,
        cache_dim: int = 8,
        cache_distance_threshold: float = 0.15,
        residency_zone: str = "on-prem-sovereign",
        dim: Optional[int] = None,
        distance_threshold: Optional[float] = None,
        block_pii: Optional[bool] = None,
    ) -> None:
        try:
            super().__init__()
        except Exception:
            pass
        eff_dim = int(dim) if dim is not None else int(cache_dim)
        eff_thresh = float(distance_threshold) if distance_threshold is not None else float(cache_distance_threshold)
        eff_policy = ("block" if block_pii else "audit") if block_pii is not None else str(pii_policy)
        self._delegate: Any = None
        self.num_workers = int(num_workers)
        self.max_tokens = int(max_tokens)
        self.pii_policy = str(eff_policy)
        self.enable_semantic_cache = bool(enable_semantic_cache)
        self.cache_dim = int(eff_dim)
        self.cache_distance_threshold = float(eff_thresh)
        self.residency_zone = str(residency_zone)

    def _get_delegate(self) -> Any:
        if self._delegate is None:
            mod_json = _load_peer_json_module()
            self._delegate = mod_json.SiliciumLiteLLMGateway(
                num_workers=self.num_workers,
                max_tokens=self.max_tokens,
                pii_policy=self.pii_policy,
                enable_semantic_cache=self.enable_semantic_cache,
                cache_dim=self.cache_dim,
                cache_distance_threshold=self.cache_distance_threshold,
                residency_zone=self.residency_zone,
            )
        return self._delegate

    def __call__(
        self,
        request_payload: Any = None,
        raise_on_block: bool = False,
        data: Any = None,
        call_type: Any = None,
    ) -> Any:
        if request_payload is None and data is None and call_type is None:
            return self
        return self.pre_call_hook(
            request_payload=request_payload,
            raise_on_block=raise_on_block,
            data=data,
            call_type=call_type,
        )

    def inspect_and_route(
        self,
        request_payload: Any,
        raise_on_block: bool = False,
    ) -> Dict[str, Any]:
        return dict(self._get_delegate().inspect_and_route(request_payload, raise_on_block=raise_on_block))

    def mask_sensitive_payload(self, payload_str: str) -> str:
        return str(self._get_delegate().mask_sensitive_payload(payload_str))

    def pre_call_hook(
        self,
        request_payload: Any = None,
        raise_on_block: Any = False,
        data: Any = None,
        call_type: Any = None,
    ) -> Dict[str, Any]:
        res = self._get_delegate().pre_call_hook(
            request_payload=request_payload,
            raise_on_block=raise_on_block,
            data=data,
            call_type=call_type,
        )
        return res if isinstance(res, dict) else dict(res)

    async def async_pre_call_hook(
        self,
        request_payload: Any = None,
        raise_on_block: Any = False,
        data: Any = None,
        call_type: Any = None,
    ) -> Dict[str, Any]:
        res = await self._get_delegate().async_pre_call_hook(
            request_payload=request_payload,
            raise_on_block=raise_on_block,
            data=data,
            call_type=call_type,
        )
        return res if isinstance(res, dict) else dict(res)

    def post_call_hook(
        self,
        request_payload: Any,
        response_obj: Any = None,
        prompt: Any = "",
        end_time: Any = None,
    ) -> Dict[str, Any]:
        return dict(
            self._get_delegate().post_call_hook(
                request_payload,
                response_obj=response_obj,
                prompt=prompt,
                end_time=end_time,
            )
        )

    def log_success_event(
        self,
        request_payload: Any,
        response_obj: Any = None,
        prompt: Any = "",
        end_time: Any = None,
    ) -> Dict[str, Any]:
        return dict(
            self._get_delegate().log_success_event(
                request_payload,
                response_obj=response_obj,
                prompt=prompt,
                end_time=end_time,
            )
        )

    async def async_log_success_event(
        self,
        request_payload: Any,
        response_obj: Any = None,
        prompt: Any = "",
        end_time: Any = None,
    ) -> Dict[str, Any]:
        return dict(
            await self._get_delegate().async_log_success_event(
                request_payload,
                response_obj=response_obj,
                prompt=prompt,
                end_time=end_time,
            )
        )


def generate_litellm_config_yaml(
    model_name: str = "gpt-4o-mini",
    pii_policy: str = "block",
) -> str:
    """Generate a turnkey `litellm_config.yaml` wiring `silicium_json.litellm_gateway` / `silicium_ai_ops.litellm_gateway` (`SAO-GATEWAY-LITELLM-001`)."""
    mod_json = _load_peer_json_module()
    return str(mod_json.generate_litellm_config_yaml(model_name=model_name, pii_policy=pii_policy))


litellm_gateway: SiliciumLiteLLMGateway = SiliciumLiteLLMGateway()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="silicium-vector", description="Silicium Vector Pro & Enterprise CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_st = sub.add_parser("status", help="Display license slot, vCPU cap, session quota, and SIMD ISA telemetry")
    p_st.add_argument("--json", action="store_true", help="Emit JSON output")
    p_st.add_argument("--prometheus", action="store_true", help="Emit OpenMetrics / Prometheus text format")
    p_st.add_argument("--otel-json", action="store_true", help="Emit OpenTelemetry Span attributes JSON")

    p_roi = sub.add_parser("roi", help="Calculate memory footprint and optimal GitHub Sponsors Enterprise Slot")
    p_roi.add_argument("--vectors", type=int, default=1000000)
    p_roi.add_argument("--dim", type=int, default=1536)
    p_roi.add_argument("--vcpus", type=int, default=64)
    p_roi.add_argument("--nodes", type=int, default=1)
    p_roi.add_argument("--gb-per-hour", type=float, default=0.0)
    p_roi.add_argument("--gb-per-day", type=float, default=0.0)
    p_roi.add_argument("--json", action="store_true", help="Emit JSON output")

    p_ins = sub.add_parser("inspect", help="Inspect a saved SILICM_HNSW_V01 index file")
    p_ins.add_argument("path")
    p_ins.add_argument("--json", action="store_true", help="Emit JSON output")

    p_bench = sub.add_parser("bench", help="Run an in-memory HNSW micro-benchmark")
    p_bench.add_argument("--count", type=int, default=2000)
    p_bench.add_argument("--dim", type=int, default=64)
    p_bench.add_argument("--k", type=int, default=10)
    p_bench.add_argument("--json", action="store_true", help="Emit JSON output")

    p_ht = sub.add_parser(
        "host-token",
        help="Display the 21-character public HOST-<16HEX> activation token for v3 Biometric Passport minting",
    )
    p_ht.add_argument("--json", action="store_true", help="Emit JSON output")

    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.cmd == "host-token":
        tok = host_token()
        print(json.dumps({"host_token": tok, "engine": "silicium-vector"}) if args.json else tok)
        return 0
    if args.cmd == "roi":
        data = estimate_finops_roi(
            vectors=args.vectors,
            dim=args.dim,
            vcpus=args.vcpus,
            nodes=args.nodes,
            gb_per_hour=args.gb_per_hour,
            gb_per_day=args.gb_per_day,
        )
        if args.json:
            print(json.dumps(data))
        else:
            print(
                f"Slot {data['recommended_slot']} ({data['slot_label']}): "
                f"{data['slot_max_vcpus']} vCPUs — ${data['monthly_price_usd']}/mo ({data['sponsors_url']})"
            )
        return 0
    if args.cmd == "inspect":
        idx = Index.from_file(args.path)
        info = idx.info()
        print(json.dumps(info) if args.json else str(info))
        return 0
    if args.cmd == "bench":
        rng = np.random.default_rng(42)
        vecs = rng.standard_normal((args.count, args.dim), dtype=np.float32)
        idx = Index(dim=args.dim, space="l2", m=16, ef_construction=64)
        idx.add(vecs)
        hits = idx.search(vecs[:16], k=args.k)
        res = {"count": len(idx), "dim": args.dim, "k": args.k, "queries_tested": int(hits.shape[0])}
        print(json.dumps(res) if args.json else str(res))
        return 0

    if getattr(args, "otel_json", False):
        print(json.dumps(otel_span_attributes()))
        return 0
    if getattr(args, "prometheus", False):
        print(prometheus_metrics(), end="")
        return 0
    st = license_status()
    if getattr(args, "json", False):
        print(json.dumps(st))
    else:
        print(f"Silicium Vector | {st['tier']} | max_vcpus={st['max_vcpus']} | ISA={st['isa']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
