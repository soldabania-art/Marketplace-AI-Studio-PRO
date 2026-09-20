"""Web Push endpoint admission and delivery guards.

Push subscription endpoints are browser-provided input.  The same checks run
when a subscription is saved and immediately before every delivery: a stored
endpoint must not turn into an internal request after a DNS change.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

import requests
from fastapi import HTTPException
from pywebpush import webpush
from requests.adapters import HTTPAdapter, TimeoutSauce
from urllib3 import HTTPSConnectionPool
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from .config import get_settings


DEFAULT_PUSH_ENDPOINT_HOSTS = frozenset({
    "fcm.googleapis.com",                 # Chromium browsers
    "updates.push.services.mozilla.com",  # Firefox
    "web.push.apple.com",                 # Safari
})


class _NoRedirectSession(requests.Session):
    """A push endpoint is never allowed to select a second destination."""

    def request(self, method, url, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)


class _PinnedPushAdapter(HTTPAdapter):
    """Connect to a checked address while retaining hostname TLS validation."""

    def send(self, request, **kwargs):
        host, addresses = validate_push_endpoint(request.url)
        timeout = kwargs.get("timeout")
        if isinstance(timeout, tuple):
            timeout = TimeoutSauce(connect=timeout[0], read=timeout[1])
        elif not isinstance(timeout, TimeoutSauce):
            timeout = TimeoutSauce(connect=timeout, read=timeout)
        # Pinning the connection to this just-resolved IP removes the DNS
        # rebinding race. SNI and certificate verification use the host.
        pool = HTTPSConnectionPool(addresses[0], port=443, cert_reqs="CERT_REQUIRED", assert_hostname=host, server_hostname=host)
        try:
            headers = request.headers.copy()
            headers["Host"] = host
            response = pool.urlopen(
                request.method, request.path_url, body=request.body, headers=headers,
                redirect=False, retries=False, timeout=timeout, preload_content=True,
            )
            return self.build_response(request, response)
        except Urllib3HTTPError as exc:
            raise WebPushException("Push delivery failed") from exc
        finally:
            pool.close()


def _allowed_hosts() -> set[str]:
    configured = get_settings().push_endpoint_host_set
    return configured or set(DEFAULT_PUSH_ENDPOINT_HOSTS)


def _resolve_public_addresses(host: str) -> tuple[str, ...]:
    try:
        rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("push endpoint host cannot be resolved") from exc
    addresses = {row[4][0] for row in rows}
    if not addresses:
        raise ValueError("push endpoint host has no addresses")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("push endpoint returned an invalid address") from exc
        if not ip.is_global or ip.is_reserved:
            raise ValueError("push endpoint resolves to a non-public address")
        if ip.is_multicast:
            raise ValueError("push endpoint resolves to a multicast address")
    return tuple(sorted(addresses))


def validate_push_endpoint(endpoint: str) -> tuple[str, tuple[str, ...]]:
    parsed = urlsplit(endpoint)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or host not in _allowed_hosts()
    ):
        raise ValueError("unsupported push endpoint")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("push endpoint must use an approved hostname")
    return host, _resolve_public_addresses(host)


def require_safe_push_endpoint(endpoint: str) -> None:
    try:
        validate_push_endpoint(endpoint)
    except (ValueError, socket.gaierror):
        raise HTTPException(400, "Некорректный PUSH endpoint.") from None


def send_web_push(*, endpoint: str, keys: dict[str, str], data: str, vapid_private_key: str, vapid_subject: str, ttl: int):
    """Pin every delivery to a just-validated address and reject redirects."""
    validate_push_endpoint(endpoint)
    with _NoRedirectSession() as session:
        session.trust_env = False
        session.mount("https://", _PinnedPushAdapter())
        return webpush(
            subscription_info={"endpoint": endpoint, "keys": keys},
            data=data,
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_subject},
            timeout=get_settings().push_request_timeout_seconds,
            ttl=ttl,
            requests_session=session,
        )
