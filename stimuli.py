"""Image stimulus support.

Qualtrics surveys embed image stimuli (ads, product photos) as ``<img>`` tags
inside question/descriptive-text HTML. ``qualtrics_client`` strips HTML before
the LLM sees the text, so image URLs are extracted here first and carried on
``Question.image_urls``. The LLM clients then fetch the bytes (cached per URL —
the same stimulus is shown to every persona) and attach them as multimodal
content parts.
"""
from __future__ import annotations

import base64
import html as html_mod
import re
import ssl
from functools import lru_cache
from urllib.parse import urlsplit

import truststore

_IMG_SRC_RE = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)

# Qualtrics graphics are typically well under 1 MB; anything bigger than this
# is a misconfigured stimulus and would blow up request payloads.
MAX_IMAGE_BYTES = 15 * 1024 * 1024

_EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def extract_image_urls(html: str, origin: str = "") -> list[str]:
    """Pull ``<img src>`` URLs out of a Qualtrics HTML fragment, in order.

    Relative URLs (e.g. ``/ControlPanel/Graphic.php?IM=IM_xxx``) are resolved
    against ``origin`` (``https://{datacenter}.qualtrics.com``); if no origin is
    known they are dropped rather than passed on broken. Duplicates are removed
    while preserving first-seen order.
    """
    urls: list[str] = []
    for src in _IMG_SRC_RE.findall(html or ""):
        src = html_mod.unescape(src).strip()
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            if not origin:
                continue
            src = origin.rstrip("/") + src
        elif not src.lower().startswith(("http://", "https://", "data:image/")):
            continue
        if src not in urls:
            urls.append(src)
    return urls


def origin_of(url: str) -> str:
    """``https://yul1.qualtrics.com/API/v3`` → ``https://yul1.qualtrics.com``."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


@lru_cache(maxsize=128)
def fetch_image(url: str) -> tuple[bytes, str]:
    """Download an image and return ``(bytes, mime_type)``. Cached per URL.

    Raises on network errors, non-2xx responses, or oversized images — callers
    degrade gracefully (the question is still asked, minus the image).
    """
    if url.startswith("data:image/"):
        header, _, payload = url.partition(",")
        mime = header[len("data:"):].split(";")[0]
        data = base64.b64decode(payload)
    else:
        resp = _http().get(url, timeout=30)
        resp.raise_for_status()
        data = resp.content
        mime = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if not mime.startswith("image/"):
            mime = _mime_from_url(url) or "image/png"
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"image at {url} is {len(data)} bytes (max {MAX_IMAGE_BYTES})")
    return data, mime


def image_data_url(url: str) -> str:
    """Fetch an image and return it as a ``data:`` URL for OpenAI-style APIs."""
    data, mime = fetch_image(url)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


@lru_cache(maxsize=1)
def _http():
    """httpx client with the OS trust store — same TLS setup as
    openrouter_client, needed on machines with corporate certificates."""
    import httpx

    return httpx.Client(
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        timeout=30.0,
        follow_redirects=True,
        # Some image CDNs (e.g. Wikimedia) reject default library user-agents.
        headers={"User-Agent": "doppelganger-stimuli/1.0 (survey pretest; image fetch)"},
    )


def _mime_from_url(url: str) -> str | None:
    path = urlsplit(url).path.lower()
    for ext, mime in _EXT_TO_MIME.items():
        if path.endswith(ext):
            return mime
    return None
