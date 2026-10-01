"""Hatch gateway Noise_XX session.

The open Muse page tunnels HTTP over a Noise_XX_25519_AESGCM_SHA256 WebSocket
at wss://hatch.metaaivm.com/v1/noise. The handshake matches that page: the
protocol name is hashed as the empty prologue, and AES-GCM nonces are
big-endian. This module never logs the URL, because the query carries the token.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import socket
import ssl
import struct
import uuid
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PROTOCOL = b"Noise_XX_25519_AESGCM_SHA256"
_EMPTY = b""
DAEMON = "daemon"
SENTINEL = "sentinel"
_SERVICE = {DAEMON: 0, SENTINEL: 1, "vault": 2, "authd": 3}


class NoiseError(Exception):
    pass


def _hmac(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def _hkdf(ck: bytes, ikm: bytes, count: int) -> list[bytes]:
    temp = _hmac(ck, ikm)
    out: list[bytes] = []
    prev = b""
    for index in range(1, count + 1):
        prev = _hmac(temp, prev + bytes([index]))
        out.append(prev)
    return out


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _nonce(counter: int) -> bytes:
    return b"\x00\x00\x00\x00" + struct.pack(">II", (counter >> 32) & 0xFFFFFFFF, counter & 0xFFFFFFFF)


class _Cipher:
    def __init__(self) -> None:
        self._key: bytes | None = None
        self._n = 0

    def initialize(self, key: bytes) -> None:
        self._key = key
        self._n = 0

    def encrypt(self, ad: bytes, plaintext: bytes) -> bytes:
        if self._key is None:
            return plaintext
        if self._n >= 2**53:
            raise NoiseError("nonce exhausted")
        box = AESGCM(self._key)
        out = box.encrypt(_nonce(self._n), plaintext, ad)
        self._n += 1
        return out

    def decrypt(self, ad: bytes, ciphertext: bytes) -> bytes:
        if self._key is None:
            return ciphertext
        if self._n >= 2**53:
            raise NoiseError("nonce exhausted")
        box = AESGCM(self._key)
        out = box.decrypt(_nonce(self._n), ciphertext, ad)
        self._n += 1
        return out


class _Symmetric:
    def __init__(self) -> None:
        name = PROTOCOL
        if len(name) > 32:
            raise NoiseError("protocol name")
        self.h = name + bytes(32 - len(name))
        self.ck = self.h
        self.cipher = _Cipher()

    def mix_hash(self, data: bytes) -> None:
        self.h = _sha256(self.h + data)

    def mix_key(self, ikm: bytes) -> None:
        self.ck, key = _hkdf(self.ck, ikm, 2)
        self.cipher = _Cipher()
        self.cipher.initialize(key)

    def encrypt_and_hash(self, plaintext: bytes) -> bytes:
        out = self.cipher.encrypt(self.h, plaintext)
        self.mix_hash(out)
        return out

    def decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        out = self.cipher.decrypt(self.h, ciphertext)
        self.mix_hash(ciphertext)
        return out

    def split(self) -> tuple[_Cipher, _Cipher]:
        first, second = _hkdf(self.ck, _EMPTY, 2)
        send, recv = _Cipher(), _Cipher()
        send.initialize(first)
        recv.initialize(second)
        return send, recv


def _pub(private: X25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _dh(private: X25519PrivateKey, public: bytes) -> bytes:
    if len(public) != 32:
        raise NoiseError("x25519 public key")
    shared = private.exchange(X25519PublicKey.from_public_bytes(public))
    if shared == bytes(32):
        raise NoiseError("x25519")
    return shared


def _varint(value: int) -> bytes:
    value &= (1 << 64) - 1
    out = bytearray()
    while True:
        piece = value & 0x7F
        value >>= 7
        if value:
            out.append(piece | 0x80)
        else:
            out.append(piece)
            return bytes(out)


def _read_varint(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while index < len(data):
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7
        if shift > 63:
            raise NoiseError("varint")
    raise NoiseError("varint")


def _key(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _field_bytes(field: int, payload: bytes) -> bytes:
    return _key(field, 2) + _varint(len(payload)) + payload


def _field_str(field: int, text: str) -> bytes:
    return _field_bytes(field, text.encode("utf-8"))


def _field_varint(field: int, value: int) -> bytes:
    return _key(field, 0) + _varint(value)


def _decode(data: bytes) -> list[tuple[int, bytes | int]]:
    index = 0
    found: list[tuple[int, bytes | int]] = []
    while index < len(data):
        key, index = _read_varint(data, index)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, index = _read_varint(data, index)
            found.append((field, value))
        elif wire == 2:
            length, index = _read_varint(data, index)
            end = index + length
            if end > len(data):
                raise NoiseError("length")
            found.append((field, data[index:end]))
            index = end
        else:
            raise NoiseError("wire")
    return found


def _freshness(nonce: bytes) -> bytes:
    return _field_bytes(1, nonce)


def _header(key: str, value: str) -> bytes:
    return _field_str(1, key) + _field_str(2, value)


def _request_message(verb: str, path: str, headers: list[tuple[str, str]], body: bytes) -> bytes:
    out = _field_str(1, verb) + _field_str(2, path)
    for key, value in headers:
        out += _field_bytes(3, _header(key, value))
    if body:
        out += _field_bytes(4, body)
    out += _field_varint(5, 1)
    return out


def _service_frame(stream_id: int, request: bytes) -> bytes:
    return _field_varint(1, stream_id) + _field_bytes(2, request)


def _service_request(service: str, frame: bytes) -> bytes:
    code = _SERVICE[service]
    out = b""
    if code:
        out += _field_varint(1, code)
    return out + _field_bytes(2, frame)


def _transport_frame(chunk_id: int, payload: bytes) -> bytes:
    return _field_varint(1, chunk_id) + _field_varint(2, 0) + _field_varint(3, 1) + _field_bytes(4, payload)


def _bool_field(fields: list[tuple[int, bytes | int]], number: int) -> bool:
    for field, value in fields:
        if field == number and isinstance(value, int):
            return bool(value)
    return False


def _bytes_field(fields: list[tuple[int, bytes | int]], number: int) -> bytes:
    for field, value in fields:
        if field == number and isinstance(value, bytes):
            return value
    return b""


def _int_field(fields: list[tuple[int, bytes | int]], number: int, default: int = 0) -> int:
    for field, value in fields:
        if field == number and isinstance(value, int):
            return value
    return default


class _Assembler:
    def __init__(self) -> None:
        self._pending: dict[int, dict] = {}

    def push(self, frame: bytes) -> bytes | None:
        fields = _decode(frame)
        chunk_id = _int_field(fields, 1)
        index = _int_field(fields, 2)
        total = _int_field(fields, 3, 1) or 1
        payload = _bytes_field(fields, 4)
        if total < 1 or total > 256 or index >= total:
            raise NoiseError("chunk")
        bucket = self._pending.setdefault(chunk_id, {})
        bucket[index] = payload
        if len(bucket) < total:
            return None
        self._pending.pop(chunk_id, None)
        return b"".join(bucket[i] for i in range(total))


class Transport:
    def __init__(self, send: _Cipher, recv: _Cipher) -> None:
        self._send = send
        self._recv = recv
        self._assembly = _Assembler()
        self._stream = 0

    def encrypt_request(self, service: str, verb: str, path: str, headers: list[tuple[str, str]], body: bytes) -> list[bytes]:
        self._stream += 1
        request = _request_message(verb, path, headers, body)
        frame = _service_frame(self._stream, request)
        wrapped = _service_request(service, frame)
        chunk_id = int.from_bytes(os.urandom(8), "big") & ((1 << 63) - 1)
        outer = _transport_frame(chunk_id, wrapped)
        return [self._send.encrypt(_EMPTY, outer)]

    def decrypt(self, frame: bytes) -> dict | None:
        outer = self._recv.decrypt(_EMPTY, frame)
        assembled = self._assembly.push(outer)
        if assembled is None:
            return None
        service = _decode(assembled)
        payload = _bytes_field(service, 1) or _bytes_field(service, 2)
        if not payload:
            raise NoiseError("empty response")
        inner = _decode(payload)
        kind = 0
        payload = b""
        for field, value in inner:
            if field in {2, 3, 4, 5} and isinstance(value, bytes):
                kind = field
                payload = value
        stream_id = _int_field(inner, 1)
        if kind == 3:
            fields = _decode(payload)
            return {
                "case": "response",
                "stream_id": stream_id,
                "status": _int_field(fields, 1, 200),
                "body": _bytes_field(fields, 3),
                "end_body": _bool_field(fields, 4),
            }
        if kind == 4:
            fields = _decode(payload)
            return {
                "case": "body",
                "stream_id": stream_id,
                "body": _bytes_field(fields, 1),
                "end_body": _bool_field(fields, 2),
            }
        if kind == 5:
            return {"case": "reset", "stream_id": stream_id}
        if kind == 2:
            fields = _decode(payload)
            verb = _bytes_field(fields, 1).decode("utf-8", "replace")
            path = _bytes_field(fields, 2).decode("utf-8", "replace")
            return {"case": "request", "stream_id": stream_id, "verb": verb, "path": path}
        return None

    def encrypt_response(self, *, stream_id: int, status: int, body: bytes, end_body: bool = True) -> bytes:
        app = _field_varint(1, status)
        if body:
            app += _field_bytes(3, body)
        if end_body:
            app += _field_varint(4, 1)
        frame = _field_varint(1, stream_id) + _field_bytes(3, app)
        wrapped = _field_bytes(1, frame)
        chunk_id = int.from_bytes(os.urandom(8), "big") & ((1 << 63) - 1)
        outer = _transport_frame(chunk_id, wrapped)
        return self._send.encrypt(_EMPTY, outer)


class Handshake:
    """Initiator. A responder exists so tests can complete a loopback."""

    def __init__(self) -> None:
        self._sym = _Symmetric()
        self._phase = 0
        self._ephemeral: X25519PrivateKey | None = None
        self._remote_ephemeral = b""
        self._static: X25519PrivateKey | None = None

    def start(self) -> None:
        self._sym.mix_hash(_EMPTY)
        self._phase = 1

    def write_message1(self, payload: bytes | None = None) -> bytes:
        if self._phase != 1:
            raise NoiseError("message1")
        private = X25519PrivateKey.generate()
        public = _pub(private)
        self._ephemeral = private
        self._sym.mix_hash(public)
        body = payload if payload is not None else _freshness(os.urandom(32))
        boxed = self._sym.encrypt_and_hash(body)
        self._phase = 2
        return public + boxed

    def read_message2(self, message: bytes) -> bytes:
        if self._phase != 2 or self._ephemeral is None or len(message) < 96:
            raise NoiseError("message2")
        remote_e = message[:32]
        self._sym.mix_hash(remote_e)
        self._sym.mix_key(_dh(self._ephemeral, remote_e))
        remote_static = self._sym.decrypt_and_hash(message[32:80])
        self._sym.mix_key(_dh(self._ephemeral, remote_static))
        payload = self._sym.decrypt_and_hash(message[80:])
        self._remote_ephemeral = remote_e
        self._phase = 3
        return payload

    def write_message3(self, payload: bytes = b"") -> bytes:
        if self._phase != 3:
            raise NoiseError("message3")
        private = X25519PrivateKey.generate()
        public = _pub(private)
        self._static = private
        encrypted_static = self._sym.encrypt_and_hash(public)
        self._sym.mix_key(_dh(private, self._remote_ephemeral))
        encrypted_payload = self._sym.encrypt_and_hash(payload)
        self._phase = 4
        return encrypted_static + encrypted_payload

    def split(self) -> Transport:
        if self._phase != 4:
            raise NoiseError("split")
        send, recv = self._sym.split()
        self._phase = 5
        return Transport(send, recv)


class Responder:
    def __init__(self) -> None:
        self._sym = _Symmetric()
        self._ephemeral: X25519PrivateKey | None = None
        self._static: X25519PrivateKey | None = None
        self._remote_ephemeral = b""
        self._phase = 0

    def start(self) -> None:
        self._sym.mix_hash(_EMPTY)
        self._phase = 1

    def read_message1(self, message: bytes) -> bytes:
        if self._phase != 1 or len(message) < 32:
            raise NoiseError("message1")
        self._remote_ephemeral = message[:32]
        self._sym.mix_hash(self._remote_ephemeral)
        payload = self._sym.decrypt_and_hash(message[32:])
        self._phase = 2
        return payload

    def write_message2(self, payload: bytes = b"") -> bytes:
        if self._phase != 2:
            raise NoiseError("message2")
        ephemeral = X25519PrivateKey.generate()
        static = X25519PrivateKey.generate()
        self._ephemeral = ephemeral
        self._static = static
        e_pub = _pub(ephemeral)
        s_pub = _pub(static)
        self._sym.mix_hash(e_pub)
        self._sym.mix_key(_dh(ephemeral, self._remote_ephemeral))
        encrypted_static = self._sym.encrypt_and_hash(s_pub)
        self._sym.mix_key(_dh(static, self._remote_ephemeral))
        encrypted_payload = self._sym.encrypt_and_hash(payload)
        self._phase = 3
        return e_pub + encrypted_static + encrypted_payload

    def read_message3(self, message: bytes) -> bytes:
        if self._phase != 3 or self._ephemeral is None or len(message) < 48:
            raise NoiseError("message3")
        remote_static = self._sym.decrypt_and_hash(message[:48])
        self._sym.mix_key(_dh(self._ephemeral, remote_static))
        payload = self._sym.decrypt_and_hash(message[48:])
        self._phase = 4
        return payload

    def split(self) -> Transport:
        if self._phase != 4:
            raise NoiseError("split")
        send, recv = self._sym.split()
        self._phase = 5
        return Transport(recv, send)


def gateway_url(base_url: str, *, vm_id: str, token: str, app_id: str, notary_token: str | None) -> str:
    parts = urlsplit(base_url.strip())
    scheme = parts.scheme.lower()
    if scheme in {"http", "ws"}:
        secure = "ws"
    elif scheme in {"https", "wss"}:
        secure = "wss"
    else:
        raise NoiseError("base_url")
    host = parts.hostname or ""
    if not host or parts.username or parts.password:
        raise NoiseError("base_url")
    path = parts.path or "/v1/noise"
    if path in {"", "/"}:
        path = "/v1/noise"
    port = f":{parts.port}" if parts.port else ""
    request_id = str(uuid.uuid4())
    parts_q = [f"vm_id={_q(vm_id)}", f"auth_token={_q(token)}"]
    if notary_token:
        parts_q.append(f"notary_token={_q(notary_token)}")
    parts_q.append(f"app_id={_q(app_id)}")
    parts_q.append(f"request_id={_q(request_id)}")
    return f"{secure}://{host}{port}{path}?{'&'.join(parts_q)}"


def _q(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


class Socket:
    def __init__(self, raw: socket.socket) -> None:
        self._sock = raw
        self._buf = b""

    def send(self, payload: bytes) -> None:
        header = bytes([0x82])
        length = len(payload)
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", length)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._sock.sendall(header + mask + masked)

    def recv(self) -> bytes:
        while True:
            frame = self._read_frame()
            opcode, payload = frame
            if opcode == 0x2:
                return payload
            if opcode == 0x9:
                self._send_control(0xA, payload)
                continue
            if opcode == 0x8:
                raise NoiseError("socket closed")
            if opcode == 0x1:
                raise NoiseError("unexpected text frame")

    def close(self) -> None:
        try:
            self._send_control(0x8, b"")
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass

    def _send_control(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._sock.sendall(bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked)

    def _read_exact(self, count: int) -> bytes:
        while len(self._buf) < count:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise NoiseError("socket closed")
            self._buf += chunk
        out, self._buf = self._buf[:count], self._buf[count:]
        return out

    def _read_frame(self) -> tuple[int, bytes]:
        first = self._read_exact(2)
        opcode = first[0] & 0x0F
        masked = bool(first[1] & 0x80)
        length = first[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload


def open_socket(url: str, timeout: float) -> Socket:
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "wss" else 80)
    raw = socket.create_connection((host, port), timeout=timeout)
    raw.settimeout(timeout)
    if parts.scheme == "wss":
        context = ssl.create_default_context()
        raw = context.wrap_socket(raw, server_hostname=host)
    key = __import__("base64").b64encode(os.urandom(16)).decode("ascii")
    target = parts.path or "/"
    if parts.query:
        target = f"{target}?{parts.query}"
    host_header = host if not parts.port else f"{host}:{parts.port}"
    request = (
        f"GET {target} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Origin: https://muse.ai\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    raw.sendall(request.encode("ascii"))
    data = b""
    while b"\r\n\r\n" not in data:
        piece = raw.recv(4096)
        if not piece:
            raise NoiseError("socket closed")
        data += piece
        if len(data) > 65536:
            raise NoiseError("handshake")
    head = data.split(b"\r\n", 1)[0]
    if b" 101 " not in head:
        raise NoiseError("handshake")
    rest = data.split(b"\r\n\r\n", 1)[1]
    sock = Socket(raw)
    sock._buf = rest
    return sock


class Session:
    def __init__(self, base_url: str, *, vm_id: str, token: str, app_id: str, notary_token: str | None, timeout: float) -> None:
        self._url = gateway_url(base_url, vm_id=vm_id, token=token, app_id=app_id, notary_token=notary_token)
        self._app_id = app_id
        self._timeout = timeout
        self._sock: Socket | None = None
        self._transport: Transport | None = None

    def __repr__(self) -> str:
        return "Session(gateway)"

    def call(self, service: str, verb: str, path: str, *, body: bytes, accept_first: bool = False) -> tuple[int, bytes]:
        self._ensure()
        assert self._transport is not None and self._sock is not None
        headers = [
            ("x-request-id", str(uuid.uuid4())),
            ("x-app-id", self._app_id),
            ("Accept-Language", "zh-TW"),
        ]
        if body:
            headers.insert(0, ("Content-Type", "application/json"))
        frames = self._transport.encrypt_request(service, verb, path, headers, body)
        for frame in frames:
            self._sock.send(frame)
        collected = bytearray()
        status = 200
        while True:
            incoming = self._transport.decrypt(self._sock.recv())
            if incoming is None:
                continue
            if incoming["case"] == "reset":
                raise NoiseError("reset")
            if incoming["case"] == "request":
                raise NoiseError("unexpected request")
            collected.extend(incoming.get("body") or b"")
            if incoming["case"] == "response":
                status = int(incoming["status"] or 200)
                if accept_first:
                    break
            if incoming.get("end_body"):
                break
        return status, bytes(collected)

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _ensure(self) -> None:
        if self._transport is not None:
            return
        sock = open_socket(self._url, self._timeout)
        try:
            initiator = Handshake()
            initiator.start()
            sock.send(initiator.write_message1())
            initiator.read_message2(sock.recv())
            sock.send(initiator.write_message3(b""))
            self._transport = initiator.split()
            self._sock = sock
        except Exception:
            sock.close()
            raise
