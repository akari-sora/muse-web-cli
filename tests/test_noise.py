from muse_web_cli.backends.noise import Handshake, Responder, Session, gateway_url


def test_noise_xx_round_trip_carries_one_http_response():
    initiator = Handshake()
    responder = Responder()
    initiator.start()
    responder.start()
    responder.read_message1(initiator.write_message1())
    assert initiator.read_message2(responder.write_message2(b"ready")) == b"ready"
    assert responder.read_message3(initiator.write_message3(b"")) == b""
    client = initiator.split()
    server = responder.split()
    frames = client.encrypt_request("daemon", "GET", "/health", [("x-app-id", "hatch-web")], b"")
    opened = server.decrypt(frames[0])
    assert opened["case"] == "request"
    assert opened["verb"] == "GET"
    assert opened["path"] == "/health"
    reply = server.encrypt_response(stream_id=opened["stream_id"], status=200, body=b'{"ok":true}')
    got = client.decrypt(reply)
    assert got["status"] == 200
    assert got["body"] == b'{"ok":true}'
    assert got["end_body"] is True


class _Frames:
    def __init__(self, frames):
        self.frames = list(frames)

    def send(self, payload):
        return None

    def recv(self):
        if not self.frames:
            raise AssertionError("missing frame")
        return self.frames.pop(0)

    def close(self):
        return None


def test_split_response_body_is_kept_until_end():
    initiator = Handshake()
    responder = Responder()
    initiator.start()
    responder.start()
    responder.read_message1(initiator.write_message1())
    initiator.read_message2(responder.write_message2(b""))
    responder.read_message3(initiator.write_message3(b""))
    client = initiator.split()
    server = responder.split()
    first = server.encrypt_response(stream_id=1, status=200, body=b'{"a":', end_body=False)
    second = server.encrypt_response(stream_id=1, status=200, body=b'1}', end_body=True)
    session = Session(
        "https://hatch.metaaivm.com",
        vm_id="vm-unit",
        token="unit-test-token",
        app_id="hatch-web",
        notary_token=None,
        timeout=1,
    )
    session._transport = client
    session._sock = _Frames([first, second])
    status, body = session.call("daemon", "GET", "/health", body=b"")
    assert status == 200
    assert body == b'{"a":1}'
    assert "unit-test-token" not in repr(session)


def test_gateway_url_uses_the_noise_path_and_query_names():
    url = gateway_url(
        "https://hatch.metaaivm.com",
        vm_id="vm-unit",
        token="unit-test-token",
        app_id="hatch-web",
        notary_token=None,
    )
    assert url.startswith("wss://hatch.metaaivm.com/v1/noise?")
    assert "vm_id=vm-unit" in url
    assert "auth_token=" in url
    assert "app_id=hatch-web" in url
    noted = gateway_url(
        "https://hatch.metaaivm.com",
        vm_id="vm-unit",
        token="unit-test-token",
        app_id="hatch-web",
        notary_token="notary-unit",
    )
    query = noted.split("?", 1)[1].split("&")
    assert [part.split("=", 1)[0] for part in query] == [
        "vm_id",
        "auth_token",
        "notary_token",
        "app_id",
        "request_id",
    ]
