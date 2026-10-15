"""Secure image uploads: size limit, extension allow-list, magic-byte check, ClamAV scan,
random server-side filename. Fails CLOSED: if the scanner is down, the upload is refused."""
import logging
import os
import socket
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("security")

MAX_BYTES = 5 * 1024 * 1024
CHUNK = 64 * 1024


class UploadError(ValueError):
    """Raised with a user-friendly message."""


class ScannerUnavailable(RuntimeError):
    """The antivirus engine could not be reached or gave an unexpected answer."""


@dataclass
class ScanResult:
    clean: bool
    signature: str | None = None


class ClamAVScanner:
    """Talks to a running clamd daemon with its INSTREAM protocol (no extra dependencies)."""

    def __init__(self, host="127.0.0.1", port=3310, timeout=10):
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, data: bytes) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(b"zINSTREAM\0")
                for i in range(0, len(data), CHUNK):
                    chunk = data[i:i + CHUNK]
                    s.sendall(struct.pack("!I", len(chunk)) + chunk)
                s.sendall(struct.pack("!I", 0))             # zero length = end of stream
                reply = b""
                while b"\0" not in reply:
                    part = s.recv(4096)
                    if not part:
                        break
                    reply += part
        except OSError as exc:
            raise ScannerUnavailable(f"Cannot reach ClamAV at {self.host}:{self.port}: {exc}")
        text = reply.rstrip(b"\0\n").decode(errors="replace")
        if text.endswith("OK"):
            return ScanResult(True)
        if text.endswith("FOUND"):
            return ScanResult(False, text.split(":", 1)[-1].replace("FOUND", "").strip())
        raise ScannerUnavailable(f"Unexpected ClamAV reply: {text!r}")   # e.g. size limit / ERROR


class NullScanner:
    """Development only. Never enabled unless ALLOW_UNSCANNED_UPLOADS=1."""

    def scan(self, data: bytes) -> ScanResult:
        log.warning("Upload accepted WITHOUT virus scan (development mode)")
        return ScanResult(True)


def get_scanner():
    if os.environ.get("ALLOW_UNSCANNED_UPLOADS") == "1":
        return NullScanner()
    return ClamAVScanner(os.environ.get("CLAMAV_HOST", "127.0.0.1"),
                         int(os.environ.get("CLAMAV_PORT", "3310")))


def _matches_signature(ext: str, data: bytes) -> bool:
    if ext in (".jpg", ".jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def process_upload(filename: str, data: bytes, scanner, upload_dir="uploads") -> str:
    """Validate, scan and store an image. Returns the stored relative path."""
    if not data:
        raise UploadError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise UploadError("Image must be 5 MB or smaller.")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise UploadError("Only JPG, PNG or WebP images are allowed.")
    if not _matches_signature(ext, data):
        raise UploadError("The file content does not match its type.")
    try:
        result = scanner.scan(data)
    except ScannerUnavailable as exc:
        log.error("Virus scanner unavailable, upload refused: %s", exc)
        raise UploadError("Uploads are temporarily unavailable. Please try again later.")
    if not result.clean:
        log.warning("Malware blocked: %s (original name %r)", result.signature, filename)
        raise UploadError("This file was rejected by our virus scanner.")
    folder = Path(upload_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{ext}"       # never trust the user's filename
    stored.write_bytes(data)
    return stored.as_posix()
