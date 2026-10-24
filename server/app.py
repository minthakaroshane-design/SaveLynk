
"""SaveLynk public-beta backend. Additional infrastructure hardening required before scale."""

import asyncio
import html
import ipaddress
import json
import logging
import re
import shutil
import socket
import tempfile
import time
import urllib.parse
import zipfile
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.background import BackgroundTask


app = FastAPI(title="SaveLynk API", docs_url=None, redoc_url=None)

limiter = Limiter(key_func=get_remote_address, headers_enabled=False)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

ALLOWED = (
    "tiktok.com", "instagram.com", "youtube.com", "youtu.be",
    "facebook.com", "fb.watch", "x.com", "twitter.com",
    "pinterest.com", "pin.it", "reddit.com", "redd.it", "v.redd.it"
)

IMAGE_CDNS = (
    "pinimg.com", "redd.it", "redditmedia.com", "redditstatic.com",
    "twimg.com", "fbcdn.net", "cdninstagram.com", "instagram.com",
    "tiktokcdn.com", "googleusercontent.com", "ytimg.com"
)

MAX_ITEMS = 12
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024

CACHE_TTL = 120
INFO_CACHE = {}

# These limits are per Python process.
# Run one worker during beta testing.
DOWNLOAD_SLOTS = asyncio.Semaphore(2)
INFO_SLOTS = asyncio.Semaphore(4)

logger = logging.getLogger("savelynk")


class MediaRequest(BaseModel):
    url: str = Field(min_length=12, max_length=2048)
    quality: str = "best"
    zip: bool = False


def host_allowed(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def safe_url(url, domains=ALLOWED):
    try:
        p = urllib.parse.urlsplit(url.strip())
        host = (p.hostname or "").lower().rstrip(".")

        if (
            p.scheme != "https"
            or p.username
            or p.password
            or p.port not in (None, 443)
            or not host_allowed(host, domains)
        ):
            raise ValueError("Invalid URL")

        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)

        if not addresses or any(
            not ipaddress.ip_address(a[4][0]).is_global
            for a in addresses
        ):
            raise ValueError("Nonpublic IP")

        return url.strip(), host

    except (ValueError, OSError):
        raise HTTPException(
            400,
            "Use a public HTTPS URL from a supported platform."
        )


def platform(host):
    for part, name in [
        ("tiktok", "TikTok"),
        ("instagram", "Instagram"),
        ("youtu", "YouTube"),
        ("facebook", "Facebook"),
        ("fb.watch", "Facebook"),
        ("x.com", "X"),
        ("twitter", "X"),
        ("pinterest", "Pinterest"),
        ("pin.it", "Pinterest"),
        ("reddit", "Reddit"),
    ]:
        if part in host:
            return name

    return "Media"


async def ytdlp(args, timeout=90):
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--no-config",
            "--no-cache-dir",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError:
        raise HTTPException(
            503,
            "Downloader is not installed on the server."
        )

    try:
        out, err = await asyncio.wait_for(
            proc.communicate(),
            timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise HTTPException(
            504,
            "The source took too long to respond."
        )

    if proc.returncode:
        message = err.decode(
            "utf-8", "replace"
        ).strip().splitlines()

        logger.warning(
            "yt-dlp failed: %s",
            message[-1][:200] if message else "unknown"
        )

        raise HTTPException(
            422,
            "The source could not be downloaded. Try another public link."
        )

    return out.decode("utf-8", "replace")


async def resolve_short(url):
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=False,
        trust_env=False
    ) as client:

        for _ in range(5):
            url, _ = safe_url(url)

            r = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if r.status_code not in (301, 302, 303, 307, 308):
                return url

            url = urllib.parse.urljoin(
                url,
                r.headers.get("location", "")
            )

    raise HTTPException(
        422,
        "Too many redirects in this link."
    )


def image_from_metadata(meta):
    if str(meta.get("ext") or "").lower() in (
        "jpg", "jpeg", "png", "webp", "gif"
    ):
        return meta.get("url")

    return None


async def fallback_images(url, host):
    name = platform(host)

    if name not in (
        "Pinterest", "Reddit", "X", "Instagram", "Facebook"
    ):
        return None

    if host in ("pin.it", "redd.it") or host.endswith(".pin.it"):
        url = await resolve_short(url)
        _, host = safe_url(url)

    if name == "Reddit":
        p = urllib.parse.urlsplit(url)

        if "/comments/" in p.path:
            api_url = urllib.parse.urlunsplit((
                "https",
                host,
                p.path.rstrip("/") + ".json",
                "",
                ""
            ))

            async with httpx.AsyncClient(
                timeout=12,
                follow_redirects=False,
                trust_env=False
            ) as client:
                r = await client.get(
                    api_url,
                    headers={
                        "User-Agent": "SaveLynkPublicBeta/1.0"
                    }
                )

            if r.status_code == 200:
                try:
                    post = r.json()[0]["data"]["children"][0]["data"]

                    gallery = post.get("gallery_data") or {}
                    metadata = post.get("media_metadata") or {}

                    images = []

                    for item in gallery.get("items", [])[:MAX_ITEMS]:
                        source = metadata.get(
                            item.get("media_id"), {}
                        ).get("s", {})

                        candidate = (
                            source.get("u") or source.get("gif")
                        )

                        if candidate:
                            images.append(html.unescape(candidate))

                    if not images:
                        candidate = (
                            post.get("url_overridden_by_dest") or ""
                        )

                        if re.search(
                            r"\.(?:jpe?g|png|webp|gif)(?:\?|$)",
                            candidate,
                            re.I
                        ):
                            images.append(candidate)

                    if images:
                        return {
                            "title": post.get("title") or "Reddit images",
                            "images": images,
                            "uploader": post.get("author") or ""
                        }

                except (
                    KeyError, IndexError, TypeError, ValueError
                ):
                    pass

    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=False,
        trust_env=False
    ) as client:

        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        ) as r:

            if (
                r.status_code != 200
                or "text/html" not in r.headers.get(
                    "content-type", ""
                )
            ):
                return None

            chunks = []
            total = 0

            async for chunk in r.aiter_bytes():
                total += len(chunk)

                if total > 3_000_000:
                    return None

                chunks.append(chunk)

    page = b"".join(chunks).decode("utf-8", "replace")

    def og(key):
        for tag in re.findall(
            r"<meta\b[^>]*>",
            page,
            flags=re.I
        ):
            attrs = dict(
                (k.lower(), html.unescape(v))
                for k, v in re.findall(
                    r"""([\w:-]+)\s*=\s*["']([^"']*)["']""",
                    tag
                )
            )

            if (
                attrs.get("property") == key
                or attrs.get("name") == key
            ):
                return attrs.get("content", "")

        return ""

    candidate = og("og:image") or og("twitter:image")

    if candidate:
        return {
            "title": og("og:title") or (
                f"{name} image (preview quality)"
            ),
            "images": [candidate],
            "uploader": ""
        }

    return None


async def extract(url, host):
    try:
        raw = await ytdlp(
            [
                "--no-playlist",
                "--skip-download",
                "--dump-single-json",
                "--no-warnings",
                "--socket-timeout",
                "15",
                url
            ],
            75
        )

        meta = json.loads(raw)
        entries = meta.get("entries") or []

        if entries:
            imgs = [
                image_from_metadata(e)
                for e in entries
                if isinstance(e, dict)
            ]

            if imgs and all(imgs):
                return {
                    "title": meta.get("title") or "Photo gallery",
                    "images": imgs[:MAX_ITEMS],
                    "uploader": meta.get("uploader") or ""
                }, None

        img = image_from_metadata(meta)

        if img:
            return {
                "title": meta.get("title") or "Image",
                "images": [img],
                "uploader": meta.get("uploader") or ""
            }, None

        return None, meta

    except (
        HTTPException,
        ValueError,
        json.JSONDecodeError
    ) as err:

        try:
            fallback = await fallback_images(url, host)

            if fallback:
                return fallback, None

        except (
            httpx.HTTPError,
            HTTPException,
            ValueError
        ):
            pass

        if isinstance(err, HTTPException):
            raise err

        raise HTTPException(
            422,
            "Could not read source metadata."
        )


@app.post("/api/info")
@limiter.limit("10/minute")
async def info(
    request: FastAPIRequest,
    req: MediaRequest
):
    url, host = safe_url(req.url)

    async with INFO_SLOTS:
        now = time.monotonic()

        if len(INFO_CACHE) > 200:
            INFO_CACHE.clear()

        cached = INFO_CACHE.get(url)

        if cached and cached[0] > now:
            return dict(cached[1], cached=True)

        images, meta = await extract(url, host)

        if images:
            result = {
                "title": images["title"],
                "thumbnail": images["images"][0],
                "duration": None,
                "uploader": images.get("uploader"),
                "platform": platform(host),
                "count": len(images["images"]),
                "type": "image",
                "qualities": [
                    {
                        "value": "best",
                        "label": "Best accessible image"
                    }
                ],
                "note": (
                    "Preview resolution or incomplete "
                    "galleries are possible."
                )
            }

        else:
            entries = meta.get("entries") or []
            formats = meta.get("formats") or []

            heights = sorted(
                {
                    f.get("height")
                    for f in formats
                    if isinstance(f.get("height"), int)
                    and f.get("height") > 0
                },
                reverse=True
            )

            qualities = [
                {
                    "value": "best",
                    "label": "Best available (recommended)"
                }
            ]

            qualities += [
                {
                    "value": str(h),
                    "label": f"{h}p"
                }
                for h in heights[:12]
            ]

            result = {
                "title": (
                    meta.get("title")
                    or meta.get("fulltitle")
                    or "Media"
                ),
                "thumbnail": meta.get("thumbnail"),
                "duration": meta.get("duration"),
                "uploader": meta.get("uploader"),
                "platform": platform(host),
                "count": (
                    min(len(entries), MAX_ITEMS)
                    if entries else 1
                ),
                "type": "video",
                "qualities": qualities
            }

        INFO_CACHE[url] = (
            time.monotonic() + CACHE_TTL,
            result,
            images,
            meta
        )

        return result


async def save_images(images, folder):
    semaphore = asyncio.Semaphore(4)
    totals = {"bytes": 0}

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=False,
        trust_env=False
    ) as client:

        async def fetch(i, url):
            async with semaphore:
                url, _ = safe_url(url, IMAGE_CDNS)

                async with client.stream("GET", url) as r:
                    if (
                        r.status_code != 200
                        or not r.headers.get(
                            "content-type", ""
                        ).lower().startswith("image/")
                    ):
                        raise HTTPException(
                            422,
                            "Image source did not provide "
                            "a downloadable image."
                        )

                    ext = {
                        "image/jpeg": "jpg",
                        "image/png": "png",
                        "image/webp": "webp",
                        "image/gif": "gif",
                        "image/avif": "avif"
                    }.get(
                        r.headers["content-type"].split(";")[0].lower(),
                        "jpg"
                    )

                    path = folder / (
                        f"SaveLynk_image_{i:02d}.{ext}"
                    )

                    item_bytes = 0

                    try:
                        with path.open("wb") as f:
                            async for chunk in r.aiter_bytes():
                                item_bytes += len(chunk)
                                totals["bytes"] += len(chunk)

                                if (
                                    item_bytes > MAX_IMAGE_BYTES
                                    or totals["bytes"] > MAX_TOTAL_BYTES
                                ):
                                    raise HTTPException(
                                        413,
                                        "Image download exceeds "
                                        "server limits."
                                    )

                                f.write(chunk)

                    except Exception:
                        path.unlink(missing_ok=True)
                        raise

        await asyncio.gather(
            *(
                fetch(i, url)
                for i, url in enumerate(
                    images[:MAX_ITEMS], 1
                )
            )
        )


def folder_bytes(folder):
    return sum(
        p.stat().st_size
        for p in folder.rglob("*")
        if p.is_file()
    )


@app.post("/api/download")
@limiter.limit("3/minute")
async def download(
    request: FastAPIRequest,
    req: MediaRequest
):
    url, host = safe_url(req.url)

    if (
        req.quality != "best"
        and (
            not req.quality.isdecimal()
            or not 144 <= int(req.quality) <= 4320
        )
    ):
        raise HTTPException(
            400,
            "Invalid quality."
        )

    if DOWNLOAD_SLOTS.locked():
        raise HTTPException(
            503,
            "Server is busy. Please try again shortly."
        )

    async with DOWNLOAD_SLOTS:
        folder = Path(
            tempfile.mkdtemp(prefix="savelynk_")
        )

        try:
            cached = INFO_CACHE.get(url)

            if cached and cached[0] > time.monotonic():
                images, meta = cached[2], cached[3]
            else:
                images, meta = await extract(url, host)

            if images:
                await save_images(
                    images["images"],
                    folder
                )

            else:
                selector = (
                    "bv*+ba/b"
                    if req.quality == "best"
                    else (
                        f"bv*[height<={int(req.quality)}]+ba/"
                        f"b[height<={int(req.quality)}]/best"
                    )
                )

                args = [
                    "--no-playlist",
                    "--playlist-end", str(MAX_ITEMS),
                    "--no-warnings",
                    "--no-progress",
                    "--socket-timeout", "20",
                    "--retries", "2",
                    "--fragment-retries", "2",
                    "--restrict-filenames",
                    "--paths", str(folder),
                    "-o", "%(title).90s_%(id)s.%(ext)s",
                    "-f", selector,
                    "--merge-output-format", "mp4",
                    "--max-filesize", f"{MAX_VIDEO_BYTES}",
                    url
                ]

                await ytdlp(args, 180)

            if folder_bytes(folder) > MAX_TOTAL_BYTES:
                raise HTTPException(
                    413,
                    "Download exceeds server size limit."
                )

            files = [
                f
                for f in folder.iterdir()
                if f.is_file()
                and not f.name.endswith(
                    (".part", ".ytdl")
                )
            ]

            if not files:
                raise HTTPException(
                    422,
                    "No downloadable media was returned."
                )

            if req.zip or len(files) > 1:
                path = folder / "SaveLynk_gallery.zip"

                with zipfile.ZipFile(
                    path,
                    "w",
                    zipfile.ZIP_DEFLATED,
                    compresslevel=1
                ) as archive:
                    for f in files:
                        archive.write(f, f.name)

                media = "application/zip"

            else:
                path = files[0]
                media = "application/octet-stream"

            if folder_bytes(folder) > MAX_TOTAL_BYTES * 2:
                raise HTTPException(
                    413,
                    "Archive exceeds server size limit."
                )

            return FileResponse(
                path,
                media_type=media,
                filename=path.name,
                background=BackgroundTask(
                    shutil.rmtree,
                    folder,
                    ignore_errors=True
                )
            )

        except Exception:
            shutil.rmtree(
                folder,
                ignore_errors=True
            )
            raise


@app.get("/api/health")
def health():
    return {"ok": True}
