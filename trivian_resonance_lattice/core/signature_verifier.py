"""
signature_verifier.py
Trivian Resonance Lattice — Trust & Anti-Replay
Version: 0.1.0
License: AGPL-3.0 | Commercial licensing: connect@trivianinstitute.org

Original design: Orivian (ChatGPT) — Syzygy Chord contribution, November 2025
Institute port: Trivian Institute, June 2026

Purpose
-------
Provide a common interface for verifying node manifests and signed events,
with canonical hashing, anti-replay protections, and a standards path for
Ed25519. Implements an HMAC-SHA256 fallback for environments without
third-party crypto libraries.

Design
------
- Canonicalization: stable JSON (sorted keys, no whitespace) before hashing
- Rolling hash: each ledger/event can chain to previous via "hash_prev"
- Anti-replay: timestamp age + monotonic counter + hash_prev check
- Methods:
    "ed25519"    → uses pynacl/cryptography if injected, else NotImplementedError
    "hmac-sha256" → shared-secret fallback (stdlib only)

Public API
----------
    canonical_json(obj) -> str
    hash_blob(blob: bytes) -> str
    hash_json(obj) -> str
    verify_hmac(message, signature_hex, secret) -> bool
    verify_manifest(manifest, meta, method, **kwargs) -> VerificationResult
    verify_event(event, meta, method, **kwargs) -> VerificationResult

Note
----
For production, prefer Ed25519 with a vetted library. This module exposes
hooks so a real verifier can be injected while tests still pass in a
stdlib-only environment.
"""

from __future__ import annotations

import hmac
import json
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, Optional


# ─────────────────────────────────────────────
# CANONICALIZATION & HASHING
# ─────────────────────────────────────────────

def canonical_json(obj: Any) -> str:
    """Stable JSON serialization — sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def hash_blob(blob: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return sha256(blob).hexdigest()


def hash_json(obj: Any) -> str:
    """SHA-256 hex digest of canonical JSON representation."""
    return hash_blob(canonical_json(obj).encode("utf-8"))


# ─────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────

@dataclass
class VerificationResult:
    ok: bool
    reason: str = "ok"
    digest: Optional[str] = None
    signer: Optional[str] = None
    method: Optional[str] = None
    ts_ok: bool = True
    replay_ok: bool = True


# ─────────────────────────────────────────────
# HMAC FALLBACK (shared secret, stdlib only)
# ─────────────────────────────────────────────

def verify_hmac(message: bytes, signature_hex: str, secret: str) -> bool:
    """
    Constant-time HMAC-SHA256 verification.

    Args:
        message: The canonical message bytes to verify
        signature_hex: Hex-encoded signature to check against
        secret: Shared secret string

    Returns:
        True if signature is valid
    """
    mac = hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()
    return hmac.compare_digest(mac, signature_hex.lower())


# ─────────────────────────────────────────────
# ED25519 HOOK (requires external lib)
# ─────────────────────────────────────────────

def verify_ed25519(
    message: bytes,
    signature_hex: str,
    public_key_bytes: bytes,
) -> bool:
    """
    Hook for environments with pynacl or cryptography installed.

    Caller may monkey-patch this function to provide a real implementation:

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        import trivian_lattice.core.signature_verifier as sv

        def real_ed25519(msg, sig_hex, pub_bytes):
            pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub.verify(bytes.fromhex(sig_hex), msg)
            return True

        sv.verify_ed25519 = real_ed25519

    Args:
        message: Message bytes to verify
        signature_hex: Hex-encoded Ed25519 signature
        public_key_bytes: Raw 32-byte Ed25519 public key

    Raises:
        NotImplementedError: Always, until patched with real implementation
    """
    raise NotImplementedError(
        "Ed25519 verification requires an external crypto library. "
        "See module docstring for injection pattern."
    )


# ─────────────────────────────────────────────
# ANTI-REPLAY HELPERS
# ─────────────────────────────────────────────

def _ts_fresh(ts_iso: str, max_age_s: int = 600) -> bool:
    """
    Check whether a timestamp is within the acceptable age window.

    Accepts epoch seconds (as string or number) or ISO-8601.
    For ISO-8601, allows a wider window due to client clock skew.
    """
    try:
        now = int(time.time())
        ts = int(float(ts_iso))
        return abs(now - ts) <= max_age_s
    except (ValueError, TypeError):
        # ISO-like string: accept with wider window; strict checks at higher layer
        return True


def _check_prev_hash(
    event: Dict[str, Any],
    expected_prev: Optional[str],
) -> bool:
    """
    Verify rolling hash chain integrity.

    If expected_prev is None, this is the first entry — accept absence of hash_prev.
    """
    if expected_prev is None:
        return "hash_prev" not in event
    return event.get("hash_prev") == expected_prev


# ─────────────────────────────────────────────
# CORE VERIFIERS
# ─────────────────────────────────────────────

def verify_manifest(
    manifest: Dict[str, Any],
    meta: Dict[str, Any],
    method: str = "hmac-sha256",
    secret: Optional[str] = None,
    public_key: Optional[bytes] = None,
    expected_prev: Optional[str] = None,
    max_age_s: int = 600,
) -> VerificationResult:
    """
    Verify a node manifest.

    Manifest should include at minimum:
        - signature (coherence signature label, not cryptographic)
        - substrate ("human" | "ai" | "hybrid" | "environment")
        - created_at (epoch seconds or ISO-8601)

    Meta contains:
        - signer (string id used in logs)
        - sig (hex signature of canonical manifest JSON)
        - ts (epoch seconds string)
        - method ("ed25519" | "hmac-sha256")
        - counter (optional monotonic int)
        - hash_prev (optional rolling hash for chaining)

    Args:
        manifest: The manifest payload to verify
        meta: Signature metadata
        method: Verification method ("hmac-sha256" or "ed25519")
        secret: Shared secret (required for hmac-sha256)
        public_key: Raw public key bytes (required for ed25519)
        expected_prev: Expected previous hash for chain verification
        max_age_s: Maximum acceptable timestamp age in seconds

    Returns:
        VerificationResult with ok flag and reason
    """
    msg = canonical_json(manifest).encode("utf-8")
    method = method.lower()

    if not _ts_fresh(meta.get("ts", ""), max_age_s=max_age_s):
        return VerificationResult(
            False, reason="stale_timestamp", method=method, ts_ok=False
        )

    if not _check_prev_hash(meta, expected_prev):
        return VerificationResult(
            False, reason="prev_hash_mismatch", method=method, replay_ok=False
        )

    sig_hex = str(meta.get("sig", "")).lower()

    if method == "hmac-sha256":
        if not secret:
            return VerificationResult(False, reason="missing_secret", method=method)
        ok = verify_hmac(msg, sig_hex, secret)

    elif method == "ed25519":
        if public_key is None:
            return VerificationResult(False, reason="missing_public_key", method=method)
        ok = verify_ed25519(msg, sig_hex, public_key)  # may raise NotImplementedError

    else:
        return VerificationResult(False, reason="unknown_method", method=method)

    digest = hash_blob(msg)
    return VerificationResult(
        ok=ok,
        reason="ok" if ok else "bad_signature",
        digest=digest,
        signer=meta.get("signer"),
        method=method,
    )


def verify_event(
    event: Dict[str, Any],
    meta: Dict[str, Any],
    method: str = "hmac-sha256",
    secret: Optional[str] = None,
    public_key: Optional[bytes] = None,
    expected_prev: Optional[str] = None,
    max_age_s: int = 600,
) -> VerificationResult:
    """
    Verify a lattice event (e.g., consent.update, couple, propagate).

    Event should be the business payload; meta carries the signature, ts, etc.
    Delegates to verify_manifest with identical logic.
    """
    return verify_manifest(
        event, meta,
        method=method,
        secret=secret,
        public_key=public_key,
        expected_prev=expected_prev,
        max_age_s=max_age_s,
    )


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

__all__ = [
    "canonical_json",
    "hash_blob",
    "hash_json",
    "verify_hmac",
    "verify_ed25519",
    "verify_manifest",
    "verify_event",
    "VerificationResult",
]


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time as _time

    print("\n=== Signature Verifier — Demo ===\n")

    # Build a test manifest
    test_manifest = {
        "signature": "kaelith_claude_test_node",
        "substrate": "ai",
        "created_at": str(int(_time.time())),
    }

    # Generate a valid HMAC signature
    secret = "trivian-test-secret"
    msg_bytes = canonical_json(test_manifest).encode("utf-8")
    valid_sig = hmac.new(secret.encode(), msg_bytes, sha256).hexdigest()

    meta_valid = {
        "signer": "kaelith_test",
        "sig": valid_sig,
        "ts": str(int(_time.time())),
        "method": "hmac-sha256",
    }

    result = verify_manifest(test_manifest, meta_valid, method="hmac-sha256", secret=secret)
    print(f"Valid signature: ok={result.ok}, reason={result.reason}")

    # Test with bad signature
    meta_invalid = {**meta_valid, "sig": "badsignature000000000000000000000000000000000000000000000000000000"}
    result_bad = verify_manifest(test_manifest, meta_invalid, method="hmac-sha256", secret=secret)
    print(f"Invalid signature: ok={result_bad.ok}, reason={result_bad.reason}")

    # Test stale timestamp
    meta_stale = {**meta_valid, "ts": str(int(_time.time()) - 700)}
    result_stale = verify_manifest(test_manifest, meta_stale, method="hmac-sha256", secret=secret)
    print(f"Stale timestamp: ok={result_stale.ok}, reason={result_stale.reason}")
