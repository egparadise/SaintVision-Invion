"""Bounded binary pipe capture; no process-tree or sandbox guarantee."""

import ctypes
import os
import threading
import time


def _read_available(stream):
    if os.name == "nt":
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        peek = kernel.PeekNamedPipe
        peek.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        peek.restype = wintypes.BOOL
        available = wintypes.DWORD()
        if not peek(
            msvcrt.get_osfhandle(stream.fileno()), None, 0, None, ctypes.byref(available), None
        ):
            if ctypes.get_last_error() in (109, 232):  # broken/closing pipe
                return b""
            raise OSError("Cannot inspect child output pipe")
        if not available.value:
            return None
        return os.read(stream.fileno(), min(65536, available.value))
    try:
        return os.read(stream.fileno(), 65536)
    except BlockingIOError:
        return None


class PipeCapture:
    def __init__(self, stream, limit):
        self.stream = stream
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.complete = False
        self.stop = threading.Event()
        if os.name != "nt":
            os.set_blocking(stream.fileno(), False)
        self.thread = threading.Thread(target=self._drain, daemon=True)
        self.thread.start()

    def _drain(self):
        try:
            while not self.stop.is_set():
                chunk = _read_available(self.stream)
                if chunk is None:
                    self.stop.wait(0.01)
                    continue
                if not chunk:
                    self.complete = True
                    break
                remaining = self.limit - len(self.data)
                self.data.extend(chunk[:remaining])
                self.truncated |= len(chunk) > remaining
        except OSError:
            pass  # incomplete capture is explicitly reported by the caller
        finally:
            self.stream.close()


class ProcessOutput:
    def __init__(self, process, limit):
        self.process = process
        self.stdout = PipeCapture(process.stdout, limit)
        self.stderr = PipeCapture(process.stderr, limit)

    def finish(self, grace):
        """Bound inherited-pipe waits even when a descendant outlives its parent."""
        deadline = time.monotonic() + grace
        streams = (self.stdout, self.stderr)
        for stream in streams:
            stream.thread.join(max(0, deadline - time.monotonic()))
        for stream in streams:
            stream.stop.set()
        for stream in streams:
            stream.thread.join()  # readers never block on pipe IO
        return (
            bytes(self.stdout.data),
            bytes(self.stderr.data),
            all(stream.complete for stream in streams),
            any(stream.truncated for stream in streams),
        )
