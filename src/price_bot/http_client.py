from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.6",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
}


@dataclass
class FetchResponse:
    url: str
    status: int
    content_type: str
    text: str


class FetchError(RuntimeError):
    def __init__(self, url: str, message: str, status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


class HttpClient:
    def __init__(self, timeout_seconds: int = 14):
        self.timeout_seconds = timeout_seconds

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        request_headers = dict(DEFAULT_HEADERS)
        if headers:
            request_headers.update(headers)

        req = Request(url, headers=request_headers)
        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read()
                content_type = response.headers.get("content-type", "")
                charset = response.headers.get_content_charset() or "utf-8"
                text = body.decode(charset, errors="replace")
                return FetchResponse(
                    url=response.geturl(),
                    status=response.status,
                    content_type=content_type,
                    text=text,
                )
        except HTTPError as exc:
            raise FetchError(url, f"HTTP {exc.code}", exc.code) from exc
        except (URLError, socket.timeout, TimeoutError) as exc:
            raise FetchError(url, str(exc)) from exc

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> object:
        response = self.get_text(url, headers=headers)
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise FetchError(url, "Response is not valid JSON", response.status) from exc

    def post_json(self, url: str, payload: dict[str, object], timeout_seconds: int | None = None) -> object:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
            },
        )
        try:
            with urlopen(req, timeout=timeout_seconds or self.timeout_seconds) as response:
                text = response.read().decode("utf-8", errors="replace")
                return json.loads(text)
        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            raise FetchError(url, f"HTTP {exc.code}: {body[:300]}", exc.code) from exc
        except (URLError, socket.timeout, TimeoutError) as exc:
            raise FetchError(url, str(exc)) from exc
