"""Post-audit v1 neighbors. Original payload-only F024 remains untouched."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import math
import pytest
from trivian_resonance_lattice.core.signature_verifier import (
    sign_payload, verify_event, verify_manifest, MemoryReplayStore, SQLiteReplayStore)

NOW = 1788825600
KEY = 'synthetic-post-audit-key'
EVENT = {'action': 'consent.update', 'value': True}


def signed(**kw):
    args = dict(secret=KEY, signer='alice', key_id='epoch1', counter=1, ts=NOW)
    args.update(kw)
    return sign_payload(EVENT, **args)


def verify(meta, store, **kw):
    return verify_event(EVENT, meta, secret=KEY, replay_store=store, now=NOW, **kw)

@pytest.mark.parametrize('ts', ['garbage','2026-09-08','2026-09-08T00:00:00','NaN','Infinity','',None,True,-1])
def test_F022_strict_timestamp_fails_closed(ts):
    assert not verify(signed(ts=ts), MemoryReplayStore()).ok

@pytest.mark.parametrize('ts', [NOW,str(NOW),'2026-09-08T00:00:00Z','2026-09-08T01:00:00+01:00'])
def test_F022_valid_authenticated_timestamp(ts):
    assert verify(signed(ts=ts), MemoryReplayStore()).ok

@pytest.mark.parametrize('field,value', [('ts',NOW+1),('counter',2),('signer','bob'),('key_id','epoch2'),('hash_prev','x'),('method','ed25519')])
def test_F023_each_metadata_mutation_invalidates_authentication(field,value):
    meta = signed(); meta[field] = value
    assert not verify(meta, MemoryReplayStore()).ok


def test_F023_signed_stale_message_cannot_be_refreshed():
    meta = signed(ts=NOW-601); store = MemoryReplayStore()
    assert not verify(meta, store).ok
    meta['ts'] = NOW; meta['counter'] = 2
    assert not verify(meta, store).ok

@pytest.mark.parametrize('backend', ['memory','sqlite'])
def test_F024_duplicate_counter_and_stale_counter_rejected(tmp_path, backend):
    store = MemoryReplayStore() if backend == 'memory' else SQLiteReplayStore(tmp_path/'replay.db')
    assert verify(signed(), store).ok
    assert not verify(signed(), store).ok
    assert not verify(signed(counter=0), store).ok
    assert verify(signed(counter=2), store).ok


def test_F024_sqlite_restart_and_concurrent_claims(tmp_path):
    path = tmp_path/'replay.db'; first = SQLiteReplayStore(path)
    assert verify(signed(), first).ok
    assert not verify(signed(), SQLiteReplayStore(path)).ok
    def attempt(_): return verify(signed(counter=2), SQLiteReplayStore(path)).ok
    with ThreadPoolExecutor(4) as pool: assert sum(pool.map(attempt, range(8))) == 1


def test_F024_memory_concurrent_claims():
    store = MemoryReplayStore()
    with ThreadPoolExecutor(4) as pool: assert sum(pool.map(lambda _: verify(signed(), store).ok, range(8))) == 1

@pytest.mark.parametrize('counter', [-1,True,1.5,'1',None,2**63])
def test_F024_invalid_counter(counter):
    assert not verify(signed(counter=counter), MemoryReplayStore()).ok


def test_bad_signature_does_not_consume_counter():
    store = MemoryReplayStore(); bad = signed(); bad['sig'] = '0'*64
    assert not verify(bad, store).ok
    assert verify(signed(), store).ok


def test_missing_or_unavailable_replay_state_fails_closed():
    class Broken:
        def claim(self, *args): raise OSError('unavailable')
    assert not verify(signed(), None).ok
    assert verify(signed(), Broken()).reason == 'replay_store_unavailable'


def test_key_epoch_and_message_domain_are_bound():
    store = MemoryReplayStore()
    assert verify(signed(), store).ok
    assert verify(signed(key_id='epoch2'), store).ok
    assert not verify_manifest(EVENT, signed(), secret=KEY, replay_store=store, now=NOW).ok
    meta = signed(kind='manifest')
    assert verify_manifest(EVENT, meta, secret=KEY, replay_store=store, now=NOW).ok


def test_host_signer_expectation_does_not_claim_external_identity():
    assert not verify(signed(), MemoryReplayStore(), expected_signer='bob').ok
    assert verify(signed(), MemoryReplayStore(), expected_signer='alice').ok


def test_caller_mutation_during_store_callback_cannot_rewrite_result_identity():
    meta = signed()
    class Mutating(MemoryReplayStore):
        def claim(self, *args):
            meta['signer'] = 'bob'; meta['counter'] = 100
            return super().claim(*args)
    result = verify(meta, Mutating())
    assert result.ok and result.signer == 'alice'


def test_predecessor_is_authenticated_and_checked():
    meta = signed(hash_prev='previous')
    assert not verify(meta, MemoryReplayStore()).ok
    assert verify(meta, MemoryReplayStore(), expected_prev='previous').ok
    meta['hash_prev'] = 'changed'
    assert not verify(meta, MemoryReplayStore(), expected_prev='changed').ok


def test_legacy_payload_only_signature_is_rejected_even_with_replay_store():
    import hmac, hashlib
    from trivian_resonance_lattice.core.signature_verifier import canonical_json
    meta = {'ts':NOW,'counter':1,'signer':'alice',
            'sig':hmac.new(KEY.encode(),canonical_json(EVENT).encode(),hashlib.sha256).hexdigest()}
    assert verify(meta, MemoryReplayStore()).reason == 'unauthenticated_legacy_metadata'

@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
def test_nonfinite_signed_input_cannot_be_serialized(value):
    with pytest.raises(ValueError): signed(ts=value)


def test_corrupt_replay_database_does_not_authorize(tmp_path):
    path = tmp_path/'replay.db'; store = SQLiteReplayStore(path)
    path.write_bytes(b'corrupt database')
    assert verify(signed(), store).reason == 'replay_store_unavailable'
