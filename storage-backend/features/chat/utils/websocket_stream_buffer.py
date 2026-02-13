"""Stream buffer for resilient WebSocket streaming.

Buffers streaming chunks per session to enable stream resumption after
reconnection (e.g., during backend hot-reload in development).

Key features:
- Per-session chunk buffering with sequence numbers
- TTL-based expiration (5 minutes default)
- Memory-efficient (max 1000 chunks per session)
- Automatic cleanup on completion or timeout
"""

import asyncio
import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Buffer configuration
MAX_CHUNKS_PER_SESSION = 1000  # Max chunks to buffer per session
BUFFER_TTL_SECONDS = 300  # 5 minutes (enough for hot-reload)
CLEANUP_INTERVAL_SECONDS = 60  # Clean up expired buffers every minute


class StreamBuffer:
    """Buffers streaming chunks for a single session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.chunks: deque = deque(maxlen=MAX_CHUNKS_PER_SESSION)
        self.chunk_counter = 0
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.completed = False

    def add_chunk(self, chunk: Any) -> int:
        """Add a chunk to the buffer and return its sequence number."""
        self.chunk_counter += 1
        chunk_id = self.chunk_counter
        self.last_accessed = time.time()

        # Store chunk with metadata
        self.chunks.append({"chunk_id": chunk_id, "data": chunk, "timestamp": time.time()})

        return chunk_id

    def get_chunks_after(self, last_chunk_id: Optional[int]) -> List[Dict[str, Any]]:
        """Get all chunks after the given chunk_id."""
        if last_chunk_id is None:
            # Return all chunks
            return list(self.chunks)

        # Find chunks after last_chunk_id
        result = []
        for buffered in self.chunks:
            if buffered["chunk_id"] > last_chunk_id:
                result.append(buffered)

        self.last_accessed = time.time()
        return result

    def mark_completed(self):
        """Mark stream as completed."""
        self.completed = True
        self.last_accessed = time.time()

    def is_expired(self, ttl_seconds: int = BUFFER_TTL_SECONDS) -> bool:
        """Check if buffer has expired."""
        age = time.time() - self.last_accessed
        return age > ttl_seconds

    def get_age(self) -> float:
        """Get buffer age in seconds."""
        return time.time() - self.created_at


class StreamBufferManager:
    """Global manager for all stream buffers."""

    def __init__(self):
        self.buffers: Dict[str, StreamBuffer] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Stream buffer manager started")

    async def stop(self):
        """Stop the cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Stream buffer manager stopped")

    def get_buffer(self, session_id: str) -> StreamBuffer:
        """Get or create a buffer for the session."""
        if session_id not in self.buffers:
            self.buffers[session_id] = StreamBuffer(session_id)
            logger.debug(
                "Created stream buffer for session %s (total: %d)",
                session_id[:8],
                len(self.buffers),
            )
        return self.buffers[session_id]

    def has_buffer(self, session_id: str) -> bool:
        """Check if buffer exists for session."""
        return session_id in self.buffers

    async def add_chunk(self, session_id: str, chunk: Any) -> int:
        """Add chunk to session buffer and return chunk_id."""
        async with self._lock:
            buffer = self.get_buffer(session_id)
            chunk_id = buffer.add_chunk(chunk)
            return chunk_id

    async def get_missed_chunks(
        self, session_id: str, last_chunk_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Get chunks missed since last_chunk_id."""
        async with self._lock:
            if session_id not in self.buffers:
                logger.warning(
                    "No buffer found for session %s (may have expired)", session_id[:8]
                )
                return []

            buffer = self.buffers[session_id]
            chunks = buffer.get_chunks_after(last_chunk_id)

            logger.info(
                "Retrieved %d missed chunks for session %s (after chunk_id=%s)",
                len(chunks),
                session_id[:8],
                last_chunk_id,
            )

            return chunks

    async def mark_completed(self, session_id: str):
        """Mark stream as completed."""
        async with self._lock:
            if session_id in self.buffers:
                self.buffers[session_id].mark_completed()
                logger.debug("Marked stream completed for session %s", session_id[:8])

    async def remove_buffer(self, session_id: str):
        """Remove buffer for session."""
        async with self._lock:
            if session_id in self.buffers:
                buffer = self.buffers.pop(session_id)
                logger.debug(
                    "Removed stream buffer for session %s (age: %.1fs, chunks: %d)",
                    session_id[:8],
                    buffer.get_age(),
                    len(buffer.chunks),
                )

    async def _cleanup_loop(self):
        """Periodically clean up expired buffers."""
        try:
            while True:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_expired()
        except asyncio.CancelledError:
            logger.debug("Stream buffer cleanup loop cancelled")
            raise

    async def _cleanup_expired(self):
        """Remove expired buffers."""
        async with self._lock:
            expired = []
            for session_id, buffer in self.buffers.items():
                # Remove if expired OR (completed and older than 2 minutes)
                # Extended from 60s to 120s for slow reconnects during hot-reload
                if buffer.is_expired() or (buffer.completed and buffer.get_age() > 120):
                    expired.append(session_id)

            for session_id in expired:
                buffer = self.buffers.pop(session_id)
                logger.info(
                    "Cleaned up %s stream buffer for session %s (age: %.1fs, chunks: %d)",
                    "completed" if buffer.completed else "expired",
                    session_id[:8],
                    buffer.get_age(),
                    len(buffer.chunks),
                )

            if expired:
                logger.debug(
                    "Cleaned up %d expired buffers (remaining: %d)",
                    len(expired),
                    len(self.buffers),
                )

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        total_chunks = sum(len(buffer.chunks) for buffer in self.buffers.values())
        return {
            "total_sessions": len(self.buffers),
            "total_chunks": total_chunks,
            "sessions": [
                {
                    "session_id": session_id[:8],
                    "chunks": len(buffer.chunks),
                    "age_seconds": buffer.get_age(),
                    "completed": buffer.completed,
                }
                for session_id, buffer in self.buffers.items()
            ],
        }


# Global singleton instance
_manager: Optional[StreamBufferManager] = None


def get_stream_buffer_manager() -> StreamBufferManager:
    """Get the global stream buffer manager."""
    global _manager
    if _manager is None:
        _manager = StreamBufferManager()
    return _manager


async def initialize_stream_buffer_manager():
    """Initialize and start the stream buffer manager."""
    manager = get_stream_buffer_manager()
    await manager.start()
    logger.info("Stream buffer manager initialized")


async def shutdown_stream_buffer_manager():
    """Shutdown the stream buffer manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
    logger.info("Stream buffer manager shutdown")
