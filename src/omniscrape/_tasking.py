"""Small bounded-task primitives for hard deadlines and deferred cleanup."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any, TypeVar

from .errors import BusyError

_T = TypeVar("_T")
MAX_TASK_CAPACITY = 32
_CANCELLATION_REQUESTED: set[asyncio.Task[Any]] = set()


def _request_cancel(task: asyncio.Task[Any]) -> None:
    if not task.done() and task not in _CANCELLATION_REQUESTED:
        _CANCELLATION_REQUESTED.add(task)
        task.cancel()


class BoundedTaskSet:
    """Own a fixed-capacity set of tasks until their cleanup truly finishes."""

    def __init__(self, capacity: int, *, label: str) -> None:
        if capacity < 1:
            raise ValueError("Task capacity must be positive.")
        self.capacity = capacity
        self.label = label
        self._tasks: set[asyncio.Task[Any]] = set()

    @property
    def outstanding(self) -> int:
        return len(self._tasks)

    def ensure_capacity(self) -> None:
        if len(self._tasks) >= self.capacity:
            raise BusyError(f"{self.label} cleanup capacity is temporarily unavailable.")

    def _track(self, task: asyncio.Task[Any]) -> None:
        self._tasks.add(task)

    def _discard(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)

    def snapshot(self) -> tuple[asyncio.Task[Any], ...]:
        return tuple(self._tasks)

    def cancel_active(self) -> None:
        for task in self._tasks:
            _request_cancel(task)


class BoundedAdmission:
    """Bound active work and its waiter queue to the same fixed capacity."""

    def __init__(self, capacity: int, *, label: str) -> None:
        if capacity < 1:
            raise ValueError("Admission capacity must be positive.")
        self.capacity = capacity
        self.label = label
        self._semaphore = asyncio.Semaphore(capacity)
        self._waiting = 0

    @property
    def waiting(self) -> int:
        return self._waiting

    async def acquire(self, timeout: float | None = None) -> None:
        if not self._semaphore.locked():
            await self._semaphore.acquire()
            return
        if self._waiting >= self.capacity:
            raise BusyError(f"{self.label} queue capacity is temporarily unavailable.")
        self._waiting += 1
        try:
            if timeout is None:
                await self._semaphore.acquire()
            else:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise BusyError(f"{self.label} queue wait timed out.") from exc
        finally:
            self._waiting -= 1

    def release(self) -> None:
        self._semaphore.release()


def create_bounded_task(
    operation: Coroutine[Any, Any, _T],
    *,
    registries: tuple[BoundedTaskSet, ...],
    name: str,
) -> asyncio.Task[_T]:
    """Create one task only after every local/global registry admits it."""

    try:
        for registry in registries:
            registry.ensure_capacity()
        task = asyncio.create_task(operation, name=name)
    except Exception:
        operation.close()
        raise
    for registry in registries:
        registry._track(task)

    def finished(completed: asyncio.Task[Any]) -> None:
        _CANCELLATION_REQUESTED.discard(completed)
        for registry in registries:
            registry._discard(completed)
        with contextlib.suppress(asyncio.CancelledError, Exception):
            completed.result()

    task.add_done_callback(finished)
    return task


async def await_hard_deadline(task: asyncio.Task[_T], *, timeout: float) -> _T:
    """Return at the deadline while the owning registry retains cleanup work."""

    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
    except asyncio.CancelledError:
        _request_cancel(task)
        raise
    if task not in done:
        _request_cancel(task)
        raise asyncio.TimeoutError
    return await task


async def await_retained_cleanup(
    operation: Coroutine[Any, Any, _T],
    *,
    tasks: set[asyncio.Task[Any]],
    name: str,
) -> _T:
    """Finish cleanup despite cancellation, then restore cancellation to the caller.

    Resource cleanup is kept in a separately retained task. A deadline or caller
    cancellation therefore cannot release the owning operation's capacity while
    sockets or child processes are still closing.
    """

    task = asyncio.create_task(operation, name=name)
    retain_task(task, tasks)
    interrupted: asyncio.CancelledError | None = None
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError as exc:
            if task.cancelled():
                raise
            interrupted = exc
    if interrupted is not None:
        raise interrupted
    return result


def retain_task(task: asyncio.Task[Any], tasks: set[asyncio.Task[Any]]) -> None:
    """Retain a bounded-by-caller shutdown task and consume its final outcome."""

    tasks.add(task)

    def finished(completed: asyncio.Task[Any]) -> None:
        tasks.discard(completed)
        with contextlib.suppress(asyncio.CancelledError, Exception):
            completed.result()

    task.add_done_callback(finished)


async def wait_without_cancelling(task: asyncio.Task[Any], *, timeout: float) -> bool:
    done, _ = await asyncio.wait({task}, timeout=timeout)
    if task not in done:
        return False
    await task
    return True
