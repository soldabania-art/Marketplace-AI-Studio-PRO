import socket

import pytest

from app import push_delivery


PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_rejects_unapproved_or_private_push_endpoints_without_dns_lookup(monkeypatch):
    lookups = []
    monkeypatch.setattr(push_delivery.socket, "getaddrinfo", lambda *args, **kwargs: lookups.append(args))

    for endpoint in (
        "https://127.0.0.1/push",
        "https://localhost/push",
        "https://fcm.googleapis.com@127.0.0.1/push",
        "https://fcm.googleapis.com:444/push",
        "https://example.test/push",
    ):
        with pytest.raises(ValueError):
            push_delivery.validate_push_endpoint(endpoint)
    assert lookups == []


def test_rejects_private_dns_result_before_any_delivery(monkeypatch):
    monkeypatch.setattr(push_delivery.socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443)),
    ])
    deliveries = []
    monkeypatch.setattr(push_delivery, "webpush", lambda **kwargs: deliveries.append(kwargs))

    with pytest.raises(ValueError):
        push_delivery.send_web_push(
            endpoint="https://fcm.googleapis.com/fcm/send/subscription",
            keys={"p256dh": "a" * 20, "auth": "b" * 8}, data="{}",
            vapid_private_key="test", vapid_subject="mailto:test@example.com", ttl=60,
        )
    assert deliveries == []


def test_rejects_multicast_dns_result_before_any_delivery(monkeypatch):
    monkeypatch.setattr(push_delivery.socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("224.0.0.1", 443)),
    ])
    with pytest.raises(ValueError):
        push_delivery.validate_push_endpoint("https://fcm.googleapis.com/fcm/send/subscription")


def test_delivery_revalidates_dns_and_disables_redirects(monkeypatch):
    resolutions = []
    monkeypatch.setattr(push_delivery.socket, "getaddrinfo", lambda host, *args, **kwargs: resolutions.append(host) or PUBLIC_DNS)
    captured = {}
    monkeypatch.setattr(push_delivery, "webpush", lambda **kwargs: captured.update(kwargs))

    push_delivery.send_web_push(
        endpoint="https://updates.push.services.mozilla.com/wpush/v2/subscription",
        keys={"p256dh": "a" * 20, "auth": "b" * 8}, data="{}",
        vapid_private_key="test", vapid_subject="mailto:test@example.com", ttl=60,
    )

    assert resolutions == ["updates.push.services.mozilla.com"]
    session = captured["requests_session"]
    assert captured["timeout"] == 10.0
    monkeypatch.setattr("requests.Session.request", lambda self, method, url, **kwargs: kwargs)
    assert session.request("POST", "https://updates.push.services.mozilla.com/wpush/v2/subscription")["allow_redirects"] is False


def test_pinned_adapter_connects_to_validated_ip_with_original_tls_hostname(monkeypatch):
    monkeypatch.setattr(push_delivery.socket, "getaddrinfo", lambda *args, **kwargs: PUBLIC_DNS)
    captured = {}

    class Pool:
        def __init__(self, host, **kwargs):
            captured["host"] = host
            captured.update(kwargs)

        def urlopen(self, method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured.update(kwargs)
            return type("Raw", (), {"status": 201, "reason": "Created", "headers": {}, "stream": lambda self, *args: []})()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(push_delivery, "HTTPSConnectionPool", Pool)
    import requests
    response = push_delivery._PinnedPushAdapter().send(
        requests.Request("POST", "https://fcm.googleapis.com/fcm/send/subscription", data=b"{}").prepare(), timeout=5,
    )

    assert response.status_code == 201
    assert captured["host"] == "93.184.216.34"
    assert captured["server_hostname"] == "fcm.googleapis.com"
    assert captured["assert_hostname"] == "fcm.googleapis.com"
    assert captured["headers"]["Host"] == "fcm.googleapis.com"
    assert captured["redirect"] is False
    assert captured["preload_content"] is True
    assert captured["closed"] is True
