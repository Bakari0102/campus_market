import os
import socket
import struct
import threading

import pytest

from services.upload_security import (MAX_BYTES, ClamAVScanner, NullScanner, ScannerUnavailable,
                                      ScanResult, UploadError, get_scanner, process_upload)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 50
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20


class FakeScanner:
    def __init__(self, result=ScanResult(True), error=None):
        self.result, self.error, self.calls = result, error, 0

    def scan(self, data):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


# ---------- validation ----------
@pytest.mark.parametrize("name,data", [("a.png", PNG), ("a.JPG", JPG), ("a.jpeg", JPG), ("a.webp", WEBP)])
def test_valid_images_are_stored_with_random_names(tmp_path, name, data):
    path = process_upload(name, data, FakeScanner(), tmp_path)
    assert path.endswith(name[name.rindex("."):].lower())
    stem = os.path.splitext(os.path.basename(path))[0]
    assert len(stem) == 32 and stem != os.path.splitext(name)[0]   # random name, user's discarded
    assert open(path, "rb").read() == data


@pytest.mark.parametrize("name,data,why", [
    ("a.png", b"", "empty"),
    ("a.exe", PNG, "extension"),
    ("a.png.php", PNG, "double extension"),
    ("noext", PNG, "no extension"),
    ("a.png", b"MZ" + b"\x00" * 50, "disguised executable"),
    ("a.jpg", PNG, "type mismatch"),
    ("a.png", PNG + b"x" * MAX_BYTES, "too big"),
])
def test_bad_files_rejected_before_scanning(tmp_path, name, data, why):
    scanner = FakeScanner()
    with pytest.raises(UploadError):
        process_upload(name, data, scanner, tmp_path)
    assert scanner.calls == 0, why                        # cheap checks run first


def test_infected_file_is_rejected_and_not_saved(tmp_path):
    scanner = FakeScanner(ScanResult(False, "Eicar-Test-Signature"))
    folder = tmp_path / "uploads"
    with pytest.raises(UploadError, match="virus"):
        process_upload("a.png", PNG, scanner, folder)
    assert not folder.exists() or list(folder.iterdir()) == []


def test_fails_closed_when_scanner_is_down(tmp_path):
    folder = tmp_path / "uploads"
    with pytest.raises(UploadError, match="temporarily"):
        process_upload("a.png", PNG, FakeScanner(error=ScannerUnavailable("down")), folder)
    assert not folder.exists() or list(folder.iterdir()) == []


def test_unscanned_mode_needs_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_UNSCANNED_UPLOADS", raising=False)
    assert isinstance(get_scanner(), ClamAVScanner)
    monkeypatch.setenv("ALLOW_UNSCANNED_UPLOADS", "1")
    assert isinstance(get_scanner(), NullScanner)


# ---------- ClamAV wire protocol, against a fake clamd ----------
def _read_exact(conn, n):
    buf = b""
    while len(buf) < n:
        part = conn.recv(n - len(buf))
        if not part:
            raise ConnectionError
        buf += part
    return buf


def fake_clamd(reply=None):
    """Starts a one-shot fake clamd. Returns (port, received) where received fills after the call."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    received = {}

    def serve():
        conn, _ = server.accept()
        with conn:
            received["command"] = _read_exact(conn, 10)
            payload = b""
            while True:
                (length,) = struct.unpack("!I", _read_exact(conn, 4))
                if length == 0:
                    break
                payload += _read_exact(conn, length)
            received["payload"] = payload
            conn.sendall(reply or (b"stream: Eicar-Test-Signature FOUND\0" if b"EICAR" in payload
                                   else b"stream: OK\0"))
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1], received


def test_clamav_clean_file():
    port, got = fake_clamd()
    result = ClamAVScanner(port=port, timeout=3).scan(PNG)
    assert result.clean and got["command"] == b"zINSTREAM\0" and got["payload"] == PNG


def test_clamav_detects_virus_signature():
    port, _ = fake_clamd()
    result = ClamAVScanner(port=port, timeout=3).scan(PNG + b"EICAR")
    assert not result.clean and result.signature == "Eicar-Test-Signature"


def test_clamav_large_payload_is_chunked_correctly():
    data = PNG + b"a" * 200_000                          # spans several 64 KB chunks
    port, got = fake_clamd()
    assert ClamAVScanner(port=port, timeout=3).scan(data).clean
    assert got["payload"] == data


def test_clamav_error_reply_is_treated_as_unavailable():
    port, _ = fake_clamd(reply=b"INSTREAM size limit exceeded. ERROR\0")
    with pytest.raises(ScannerUnavailable):
        ClamAVScanner(port=port, timeout=3).scan(PNG)


def test_clamav_unreachable_raises():
    with pytest.raises(ScannerUnavailable):
        ClamAVScanner(port=1, timeout=1).scan(PNG)       # nothing listens on port 1
