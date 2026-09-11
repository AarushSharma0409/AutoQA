import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit


def public_address(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        raise ValueError("Only public HTTP(S) URLs on standard ports are allowed")
    addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Private, local, reserved and metadata destinations are blocked")
    return parsed, sorted(addresses)[0]


class PinnedTLS(http.client.HTTPSConnection):
    def __init__(self, hostname, address, port):
        super().__init__(hostname, port=port, timeout=15, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), timeout=self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_public(url, max_bytes=1_000_000):
    for _ in range(6):
        parsed, address = public_address(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        conn = PinnedTLS(parsed.hostname, address, port) if parsed.scheme == "https" else http.client.HTTPConnection(address, port, timeout=15)
        try:
            path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
            conn.request("GET", path, headers={"Host": parsed.netloc, "User-Agent": "AutoAgent/1.0", "Accept-Encoding": "identity"})
            response = conn.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.getheader("Location", ""))
                continue
            if response.status >= 400:
                raise ValueError(f"Public page returned HTTP {response.status}")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError("Page exceeds retrieval limit")
            mime = response.getheader("Content-Type", "").split(";")[0]
            if mime not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError("Only HTML and text pages can be retrieved")
            return {"url": url, "body": body.decode("utf-8", errors="replace"), "mime": mime}
        finally:
            conn.close()
    raise ValueError("Too many redirects")
