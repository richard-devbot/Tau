"""Tests for tau/auth/storage.py — InMemoryAuthStorage."""
from __future__ import annotations

from tau.auth.storage import InMemoryAuthStorage
from tau.auth.types import LockResult


class TestInMemoryAuthStorage:
    def test_initial_value_is_none(self):
        s = InMemoryAuthStorage()
        result = s.with_lock(lambda v: LockResult(result=v))
        assert result.result is None

    def test_with_lock_passes_current_value(self):
        s = InMemoryAuthStorage()
        s.with_lock(lambda _: LockResult(result=None, next='{"key": "val"}'))
        result = s.with_lock(lambda v: LockResult(result=v))
        assert result.result == '{"key": "val"}'

    def test_next_updates_stored_value(self):
        s = InMemoryAuthStorage()
        s.with_lock(lambda _: LockResult(result=None, next="new-value"))
        result = s.with_lock(lambda v: LockResult(result=v))
        assert result.result == "new-value"

    def test_next_none_does_not_overwrite(self):
        s = InMemoryAuthStorage()
        s.with_lock(lambda _: LockResult(result=None, next="original"))
        s.with_lock(lambda v: LockResult(result=v, next=None))
        result = s.with_lock(lambda v: LockResult(result=v))
        assert result.result == "original"

    def test_sequential_writes(self):
        s = InMemoryAuthStorage()
        s.with_lock(lambda _: LockResult(result=None, next="first"))
        s.with_lock(lambda _: LockResult(result=None, next="second"))
        result = s.with_lock(lambda v: LockResult(result=v))
        assert result.result == "second"

    def test_result_returned_from_fn(self):
        s = InMemoryAuthStorage()
        result = s.with_lock(lambda _: LockResult(result=42))
        assert result.result == 42
