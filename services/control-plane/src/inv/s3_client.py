"""Small S3-compatible SigV4 client shared by product adapters and probes.

The client deliberately exposes only status, headers and bytes. Provider error
bodies can contain identifiers and are never propagated across this boundary.
It implements path-style requests because endpoint and bucket selection belong
to the protected Control Plane configuration, not to caller input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


@dataclass
class S3Config:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    region: str


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes

    def __init__(self, status, headers, body):
        object.__setattr__(self, "status", int(status))
        object.__setattr__(
            self, "headers", {str(key).lower(): str(value) for key, value in headers.items()}
        )
        object.__setattr__(self, "body", bytes(body))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrlLibTransport:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.opener = build_opener(_NoRedirect())

    def request(self, method, url, headers, body):
        request = Request(url, data=body if body else None, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return HttpResponse(response.status, response.headers, response.read())
        except HTTPError as error:
            # Do not retain the provider response body or message.
            return HttpResponse(error.code, {}, b"")


def _sign(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


class S3Client:
    """One canonical AWS Signature Version 4 implementation for S3 calls."""

    def __init__(self, config: S3Config, transport=None):
        self.config = config
        self.transport = transport or UrlLibTransport()

    def _request(self, method, key, body=b"", metadata_digest=None, now=None):
        now = now or datetime.now(timezone.utc)
        parsed = urlsplit(self.config.endpoint)
        host = parsed.netloc
        segments = [self.config.bucket]
        if key is not None:
            segments.extend(key.split("/"))
        canonical_uri = "/" + "/".join(
            quote(segment, safe="-_.~") for segment in segments
        )
        url = self.config.endpoint + canonical_uri
        payload_hash = hashlib.sha256(body).hexdigest()
        headers = {
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": now.strftime("%Y%m%dT%H%M%SZ"),
        }
        if metadata_digest is not None:
            headers["x-amz-meta-content-sha256"] = metadata_digest
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(
            f"{name}:{headers[name].strip()}\n" for name in sorted(headers)
        )
        canonical_request = "\n".join(
            [method, canonical_uri, "", canonical_headers, signed_names, payload_hash]
        )
        date = now.strftime("%Y%m%d")
        scope = f"{date}/{self.config.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                headers["x-amz-date"],
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        date_key = _sign(("AWS4" + self.config.secret_key).encode(), date)
        region_key = _sign(date_key, self.config.region)
        service_key = _sign(region_key, "s3")
        signing_key = _sign(service_key, "aws4_request")
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.config.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        )
        return self.transport.request(method, url, headers, body)

    def put(self, key, body, digest):
        return self._request("PUT", key, body, digest)

    def get(self, key):
        return self._request("GET", key)

    def head(self, key):
        return self._request("HEAD", key)

    def delete(self, key):
        return self._request("DELETE", key)

    def create_bucket(self):
        """Hosted disposable-lane setup helper, not a product data operation."""

        return self._request("PUT", None)
