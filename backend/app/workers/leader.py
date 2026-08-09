"""Single-leader election so only one uvicorn worker runs the scheduler."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_lock_fd = None


def acquire_worker_leadership(lock_path: Path | None = None) -> bool:
    """Try to acquire an exclusive process lock. Returns True when this process is leader."""
    global _lock_fd
    path = lock_path or Path("data/worker.leader.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    _lock_fd = open(path, "a+b")
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.seek(0)
        _lock_fd.truncate()
        _lock_fd.write(str(os.getpid()).encode())
        _lock_fd.flush()
        logger.info("Acquired worker leadership lock (%s)", path)
        return True
    except (OSError, BlockingIOError):
        _lock_fd.close()
        _lock_fd = None
        logger.info("Worker leadership lock held by another process")
        return False


def release_worker_leadership() -> None:
    global _lock_fd
    if _lock_fd is None:
        return
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    _lock_fd.close()
    _lock_fd = None
