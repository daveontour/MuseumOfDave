"""Reusable import job state management and SSE streaming."""
import json
import asyncio
import threading
from typing import Dict, Any, List

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse


class ImportJob:
    """Encapsulates all state and SSE streaming for a background import job."""

    def __init__(self, name: str, initial_progress: Dict[str, Any]):
        self.name = name
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._in_progress = False
        self._progress: Dict[str, Any] = initial_progress.copy()
        self._sse_clients: List[asyncio.Queue] = []
        self._sse_clients_lock = threading.Lock()

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._progress.copy()

    def update_state(self, **kwargs) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if key in self._progress:
                    self._progress[key] = value.copy() if isinstance(value, (list, dict)) else value

    def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        event_data = {"type": event_type, "data": data}
        message = f"data: {json.dumps(event_data)}\n\n"
        with self._sse_clients_lock:
            disconnected = []
            for q in self._sse_clients:
                try:
                    q.put_nowait(message)
                except asyncio.QueueFull:
                    pass
                except Exception:
                    disconnected.append(q)
            for q in disconnected:
                if q in self._sse_clients:
                    self._sse_clients.remove(q)

    def create_stream_response(self, request: Request) -> StreamingResponse:
        async def event_generator():
            client_queue: asyncio.Queue = asyncio.Queue()
            with self._sse_clients_lock:
                self._sse_clients.append(client_queue)
            try:
                yield f"data: {json.dumps({'type': 'progress', 'data': self.get_state()})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                        yield message
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                    except Exception:
                        break
            finally:
                with self._sse_clients_lock:
                    if client_queue in self._sse_clients:
                        self._sse_clients.remove(client_queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @property
    def in_progress(self) -> bool:
        with self._lock:
            return self._in_progress

    @property
    def cancelled(self) -> threading.Event:
        return self._cancelled

    def assert_not_running(self) -> None:
        with self._lock:
            if self._in_progress:
                raise HTTPException(
                    status_code=400,
                    detail=f"{self.name} is already in progress",
                )

    def start(self) -> None:
        with self._lock:
            self._in_progress = True
        self._cancelled.clear()

    def finish(self) -> None:
        with self._lock:
            self._in_progress = False

    def cancel(self) -> Dict[str, str]:
        with self._lock:
            if not self._in_progress:
                return {"message": f"No {self.name} in progress"}
            self._cancelled.set()
            return {"message": f"{self.name} cancellation requested"}

    def status(self) -> Dict[str, Any]:
        state = self.get_state()
        with self._lock:
            return {
                "in_progress": self._in_progress,
                "cancelled": self._cancelled.is_set(),
                **state,
            }
