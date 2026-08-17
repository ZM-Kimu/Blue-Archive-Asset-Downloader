from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

from ba_downloader.domain.models.asset import AssetCollection
from ba_downloader.domain.models.runtime import RuntimeContext


class ContextCapacityError(RuntimeError):
    pass


class ContextInUseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ApiContext:
    id: str
    context: RuntimeContext
    created_at: datetime
    last_used_at: datetime
    fingerprint: str
    catalog: AssetCollection | None = None

    @property
    def resolved(self) -> bool:
        return bool(self.context.version)


class ContextRegistry:
    def __init__(
        self,
        *,
        capacity: int = 16,
        idle_ttl: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] | None = None,
        fingerprint_key: bytes | None = None,
    ) -> None:
        self._capacity = capacity
        self._idle_ttl = idle_ttl
        self._clock = clock or (lambda: datetime.now(UTC))
        self._key = fingerprint_key or secrets.token_bytes(32)
        self._items: OrderedDict[str, ApiContext] = OrderedDict()
        self._fingerprints: dict[str, str] = {}
        self._lock = RLock()

    def create(self, context: RuntimeContext) -> tuple[ApiContext, bool]:
        now = self._clock()
        fingerprint = self._fingerprint(context.with_updates(version=""))
        with self._lock:
            self._purge_expired(now)
            existing_id = self._fingerprints.get(fingerprint)
            if existing_id is not None:
                return self._touch(existing_id, now), False
            if len(self._items) >= self._capacity:
                raise ContextCapacityError("The context registry is full.")
            item = ApiContext(uuid4().hex, context, now, now, fingerprint)
            self._items[item.id] = item
            self._fingerprints[fingerprint] = item.id
            return item, True

    def list(self) -> tuple[ApiContext, ...]:
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            return tuple(self._items.values())

    def get(self, context_id: str) -> ApiContext:
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            if context_id not in self._items:
                raise KeyError(f"Unknown context '{context_id}'.")
            return self._touch(context_id, now)

    def delete(self, context_id: str, *, in_use: bool = False) -> None:
        with self._lock:
            if in_use:
                raise ContextInUseError("Context is referenced by active work.")
            try:
                item = self._items.pop(context_id)
            except KeyError as exc:
                raise KeyError(f"Unknown context '{context_id}'.") from exc
            if self._fingerprints.get(item.fingerprint) == context_id:
                self._fingerprints.pop(item.fingerprint, None)

    def refresh(self, context_id: str) -> ApiContext:
        source = self.get(context_id)
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            if len(self._items) >= self._capacity:
                raise ContextCapacityError("The context registry is full.")
            refreshed = ApiContext(
                uuid4().hex,
                source.context.with_updates(version=""),
                now,
                now,
                source.fingerprint,
            )
            self._items[refreshed.id] = refreshed
            return refreshed

    def freeze(
        self,
        context_id: str,
        context: RuntimeContext,
        catalog: AssetCollection | None = None,
    ) -> ApiContext:
        now = self._clock()
        with self._lock:
            current = self._items[context_id]
            if current.resolved and current.context.version != context.version:
                raise ValueError("A resolved context cannot change resource version.")
            resolved_context = current.context.with_updates(version=context.version)
            updated = replace(
                current,
                context=resolved_context,
                catalog=current.catalog if catalog is None else catalog,
                last_used_at=now,
            )
            self._items[context_id] = updated
            self._items.move_to_end(context_id)
            return updated

    def _touch(self, context_id: str, now: datetime) -> ApiContext:
        current = self._items[context_id]
        touched = replace(current, last_used_at=now)
        self._items[context_id] = touched
        self._items.move_to_end(context_id)
        return touched

    def _purge_expired(self, now: datetime) -> None:
        for context_id, item in tuple(self._items.items()):
            if now - item.last_used_at >= self._idle_ttl:
                self._items.pop(context_id)
                if self._fingerprints.get(item.fingerprint) == context_id:
                    self._fingerprints.pop(item.fingerprint, None)

    def _fingerprint(self, context: RuntimeContext) -> str:
        payload = json.dumps(
            {
                "region": context.region,
                "platform": context.platform,
                "workspace": context.work_dir,
                "proxy": context.proxy_url,
                "retries": context.max_retries,
                "sqlcipher_key": context.sqlcipher_key_hex,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()
