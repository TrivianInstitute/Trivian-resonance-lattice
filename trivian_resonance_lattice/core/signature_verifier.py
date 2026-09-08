# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright © 2026 Sarasha Elion / Trivian Institute. See repository LICENSE.
# Commercial licensing: connect@trivianinstitute.org
# Original design: Orivian (ChatGPT), Syzygy Chord, November 2025
# Institute port: Trivian Institute, June 2026
"""Versioned HMAC authentication with strict freshness and atomic replay claims.

The host owns keys, the clock and replay-store lifetime. Ed25519 is an unsupported
injection hook, not an implemented algorithm. See docs/AUTHENTICATION_V1.md.
"""
from __future__ import annotations

import hmac
import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from threading import Lock
from typing import Any, Optional, Protocol

SCHEMA = "trl-auth-v1"
MAX_COUNTER = 2**63 - 1


def canonical_json(obj: Any) -> str:
    """Canonical JSON subset; non-finite numbers are not valid signed input."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hash_blob(blob: bytes) -> str:
    return sha256(blob).hexdigest()


def hash_json(obj: Any) -> str:
    return hash_blob(canonical_json(obj).encode("utf-8"))


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str = "ok"
    digest: Optional[str] = None
    signer: Optional[str] = None
    method: Optional[str] = None
    ts_ok: bool = True
    replay_ok: bool = True


def verify_hmac(message: bytes, signature_hex: str, secret: str) -> bool:
    if not isinstance(signature_hex, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", signature_hex):
        return False
    mac = hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()
    return hmac.compare_digest(mac, signature_hex.lower())


def verify_ed25519(message: bytes, signature_hex: str, public_key_bytes: bytes) -> bool:
    """Unsupported hook. There is no bundled Ed25519 implementation."""
    raise NotImplementedError("Ed25519 requires an externally supplied, vetted verifier")


class ReplayStore(Protocol):
    def claim(self, namespace: str, counter: int, digest: str) -> bool:
        """Atomically accept only a counter greater than all prior accepted counters."""
        ...


class MemoryReplayStore:
    """Process-lifetime state only. Do not replace/reset it while a key remains valid."""
    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, int] = {}

    def claim(self, namespace: str, counter: int, digest: str) -> bool:
        with self._lock:
            if counter <= self._counters.get(namespace, -1):
                return False
            self._counters[namespace] = counter
            return True


class SQLiteReplayStore:
    """Durable counter ownership across processes and restarts using one database.

    Restoring an old database is NOT a fresh authority source. The host must
    prevent rollback/deletion or retire the key epoch before accepting events.
    """
    def __init__(self, path):
        if str(path) == ":memory:":
            raise ValueError("use MemoryReplayStore for process-local state")
        self.path = str(path)
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS trl_replay_v1 (namespace TEXT PRIMARY KEY, counter INTEGER NOT NULL, digest TEXT NOT NULL)")

    def claim(self, namespace: str, counter: int, digest: str) -> bool:
        with sqlite3.connect(self.path, timeout=5) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT counter FROM trl_replay_v1 WHERE namespace = ?", (namespace,)).fetchone()
            if row is not None and counter <= row[0]:
                return False
            connection.execute("INSERT INTO trl_replay_v1 VALUES (?, ?, ?) ON CONFLICT(namespace) DO UPDATE SET counter=excluded.counter,digest=excluded.digest", (namespace, counter, digest))
            return True


def _timestamp(value):
    if type(value) in (int, float):
        parsed = float(value)
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        parsed = float(value)
    elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    else:
        raise ValueError("timestamp must be finite epoch seconds or timezone-aware RFC3339")
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError("invalid timestamp")
    return parsed


def authenticated_message(payload, meta, kind="event") -> bytes:
    """Bind every metadata field except the detached signature, plus message kind."""
    return canonical_json({"kind": kind, "payload": payload,
                           "meta": {k: v for k, v in meta.items() if k != "sig"}}).encode("utf-8")


def sign_payload(payload, *, secret: str, signer: str, key_id: str, counter: int,
                 ts=None, kind="event", hash_prev=None):
    """Create v1 metadata; verification still requires host-owned replay state."""
    meta = {"schema": SCHEMA, "method": "hmac-sha256", "signer": signer,
            "key_id": key_id, "counter": counter, "ts": time.time() if ts is None else ts}
    if hash_prev is not None:
        meta["hash_prev"] = hash_prev
    meta["sig"] = hmac.new(secret.encode(), authenticated_message(payload, meta, kind), sha256).hexdigest()
    return meta


def _verify(payload, meta, method, secret, public_key, expected_prev, max_age_s,
            replay_store, now, expected_signer, kind):
    def deny(reason, **kw):
        return VerificationResult(False, reason=reason, method=method, **kw)
    try:
        if not isinstance(payload, dict) or not isinstance(meta, dict):
            return deny("malformed_input")
        # Detach caller-owned containers before verification or store callbacks.
        payload = json.loads(canonical_json(payload))
        meta = json.loads(canonical_json(meta))
        clock = time.time() if now is None else now
        if type(clock) not in (int, float) or not math.isfinite(clock):
            return deny("invalid_clock", ts_ok=False)
        if type(max_age_s) not in (int, float) or not math.isfinite(max_age_s) or max_age_s < 0:
            return deny("invalid_age_policy", ts_ok=False)
        try:
            stamp = _timestamp(meta.get("ts"))
        except (ValueError, TypeError, OverflowError):
            return deny("malformed_timestamp", ts_ok=False)
        if not -30 <= clock - stamp <= max_age_s:
            return deny("stale_timestamp", ts_ok=False)
        if meta.get("schema") != SCHEMA:
            return deny("unauthenticated_legacy_metadata")
        if method != "hmac-sha256" or meta.get("method") != method:
            return deny("unsupported_method")
        if not isinstance(secret, str) or not secret:
            return deny("missing_secret")
        if any(not isinstance(meta.get(k), str) or not meta[k].strip() for k in ("signer", "key_id")):
            return deny("invalid_identity_label")
        if expected_signer is not None and meta["signer"] != expected_signer:
            return deny("unexpected_signer")
        counter = meta.get("counter")
        if type(counter) is not int or not 0 <= counter <= MAX_COUNTER:
            return deny("invalid_counter", replay_ok=False)
        if (expected_prev is None and "hash_prev" in meta) or (expected_prev is not None and meta.get("hash_prev") != expected_prev):
            return deny("prev_hash_mismatch", replay_ok=False)
        message = authenticated_message(payload, meta, kind)
        if not verify_hmac(message, meta.get("sig"), secret):
            return deny("bad_signature")
        if replay_store is None:
            return deny("missing_replay_store", replay_ok=False)
        # The namespace includes actual key material's fingerprint, not just a caller label.
        namespace = hash_json([SCHEMA, kind, hash_blob(secret.encode()), meta["key_id"], meta["signer"]])
        digest = hash_blob(message)
        try:
            accepted = replay_store.claim(namespace, counter, digest)
        except Exception:
            return deny("replay_store_unavailable", replay_ok=False)
        if accepted is not True:
            return deny("counter_replayed_or_stale", replay_ok=False)
        return VerificationResult(True, digest=digest, signer=meta["signer"], method=method)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return deny("malformed_input")


def verify_manifest(manifest, meta, method="hmac-sha256", secret=None, public_key=None,
                    expected_prev=None, max_age_s=600, *, replay_store=None, now=None,
                    expected_signer=None):
    return _verify(manifest, meta, method, secret, public_key, expected_prev, max_age_s,
                   replay_store, now, expected_signer, "manifest")


def verify_event(event, meta, method="hmac-sha256", secret=None, public_key=None,
                 expected_prev=None, max_age_s=600, *, replay_store=None, now=None,
                 expected_signer=None):
    return _verify(event, meta, method, secret, public_key, expected_prev, max_age_s,
                   replay_store, now, expected_signer, "event")
