# Authentication v1 — candidate 0.4.0

Decision for F022/F023/F024: payload-only signatures cannot establish freshness or replay protection. Version 0.4.0 rejects those signatures; there is no automatic migration or compatibility fallback. Re-signing requires the authorized key holder. The frozen F024 witness expects its legacy message to be accepted first, so its unchanged assertion remains red. This is disclosed separately from the new v1 replay tests, not counted as an identical-witness pass.

The signed canonical JSON contains message kind (`event` or `manifest`), payload, and every metadata field except `sig`. Required metadata: `schema=trl-auth-v1`, `method=hmac-sha256`, `signer`, `key_id`, `counter`, `ts`. Optional `hash_prev` is also signed. The authenticated digest has changed from the legacy payload digest. Canonical JSON rejects NaN and infinities.

Timestamp accepts nonnegative finite epoch seconds or timezone-aware RFC3339 with seconds. Date-only strings, naive timestamps, malformed values and booleans are rejected. Maximum age defaults to 600 seconds, with at most 30 seconds future skew. The host owns the clock and age configuration. A verifier result is an observation at verification time, not a reusable consequence-time authorization.

Counter is an integer in [0, 2^63-1]. A counter must exceed the highest accepted counter in its namespace. Namespace is schema + message kind + actual key fingerprint + authenticated key_id + authenticated signer label. Gaps are allowed; ordering inversions are rejected. The same business payload signed under a new counter is a new authenticated message, not application-level idempotency. `hash_prev` checks the host-provided expected predecessor; this module does not discover authoritative chain heads.

The caller must supply one authoritative replay store for every verifier sharing that namespace. Missing or unavailable state rejects verification. `MemoryReplayStore` survives only the lifetime of that object. `SQLiteReplayStore(path)` owns durable counters and atomically claims them across instances/processes sharing the database. Restart must reopen the same database. Deletion, rollback, independent database copies or key reuse after losing state can re-enable historical counters; the host must prevent those operations or retire the key epoch. No distributed reconciliation, backup freshness proof, migration of old state, retention eviction or global key service is implemented. Consumed counters are not rolled back after later application failure: effects require reconciliation, not blind replay.

F025 remains UNRESOLVED as an external deployment contract. Signature authentication now binds the signer *label*, and an optional host `expected_signer` rejects substitution. HMAC proves possession of a shared secret, not which person or process possessed it. Real identity requires authenticated key provisioning, principal mapping, revocation, access controls and rotation owned by a deployment. There is no bundled Ed25519 verifier; its old function remains an unsupported injection hook, and the public v1 verifier rejects unsupported algorithms.

```python
from trivian_resonance_lattice.core.signature_verifier import sign_payload, verify_event, MemoryReplayStore
key = 'synthetic-example-only'  # Deployment provisions its own secret.
store = MemoryReplayStore()  # Reuse for this key epoch; durable deployments use SQLiteReplayStore.
event = {'action': 'consent.update', 'value': True}
meta = sign_payload(event, secret=key, signer='alice', key_id='epoch1', counter=1)
assert verify_event(event, meta, secret=key, replay_store=store, expected_signer='alice').ok
assert not verify_event(event, meta, secret=key, replay_store=store, expected_signer='alice').ok
```

Tests: `tests/test_authenticated_replay.py`. They exercise strict timestamps, every authenticated metadata field, counters, concurrent claims, SQLite restart, failure of dependencies, caller mutation and message-domain separation. They do not establish external identity, deployment rollback protection or remote exactly-once effects.
