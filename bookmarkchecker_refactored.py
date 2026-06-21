#!/usr/bin/env python3
"""
bookmarkchecker_refactored.py

A less-naive bookmark checker for Chrome/Edge/Firefox exported bookmark HTML.

Goals:
- Do not treat every exception as fake HTTP 999.
- Use browser-ish headers so simple bot-blocking is less likely to create false negatives.
- Limit concurrency so we do not accidentally DDoS ourselves or trigger rate limits.
- Record final URL, redirects, elapsed time, exception class, and a human-readable live_state.
- Export directly to CSV and/or JSON without interactive prompts.

Example:
    python bookmarkchecker_refactored.py \
      -b bookmarks_6_21_26.html \
      -o bookmarkcheck_real.csv \
      --json-output bookmarkcheck_real.json \
      --concurrency 10 \
      --timeout 30 \
      --retries 1 \
      --method get \
      --ssl-fallback
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import socket
import ssl
import time
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Tag


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class BookmarkRecord:
    id: int
    title: str
    url: str
    folder_path: str = ""
    add_date_epoch: str = ""
    add_date_localtime: str = ""

    # Check result fields. Empty/None means not checked or not applicable.
    method: str = ""
    resp_code: int | None = None
    live_state: str = "unchecked"
    server_responded: bool = False
    final_url: str = ""
    redirect_chain: str = ""
    content_type: str = ""
    content_length: str = ""
    elapsed_ms: int | None = None
    attempts: int = 0
    error_type: str = ""
    exception: str = ""
    notes: str = ""


def epoch_to_localtime(epoch: str | None) -> str:
    if not epoch:
        return ""
    try:
        return datetime.fromtimestamp(int(epoch)).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return ""


def folder_path_for_anchor(anchor: Tag) -> str:
    """Best-effort folder path extraction from Netscape bookmark HTML."""
    folders: list[str] = []
    parent = anchor.parent

    while parent is not None:
        if isinstance(parent, Tag) and parent.name and parent.name.lower() == "dl":
            # BeautifulSoup's html.parser can repair Netscape bookmark HTML in a few
            # different ways. In some parsed trees the folder <H3> is inside a
            # preceding <DT>; in others it appears as the direct previous sibling.
            prev = parent.find_previous_sibling()
            h3 = None
            if isinstance(prev, Tag):
                if prev.name and prev.name.lower() == "h3":
                    h3 = prev
                else:
                    h3 = prev.find("h3", recursive=False)

            if h3:
                name = h3.get_text(" ", strip=True)
                if name:
                    folders.append(name)
        parent = parent.parent

    return "/".join(reversed(folders))


def parse_bookmark_html(bookmark_path: Path) -> list[BookmarkRecord]:
    with bookmark_path.open("r", encoding="utf-8", errors="replace") as fp:
        soup = BeautifulSoup(fp, "html.parser")

    records: list[BookmarkRecord] = []
    for idx, anchor in enumerate(soup.find_all("a")):
        if not isinstance(anchor, Tag):
            continue

        url = anchor.get("href") or ""
        add_date = anchor.get("add_date") or ""

        records.append(
            BookmarkRecord(
                id=idx,
                title=anchor.get_text(" ", strip=True),
                url=url,
                folder_path=folder_path_for_anchor(anchor),
                add_date_epoch=add_date,
                add_date_localtime=epoch_to_localtime(add_date),
            )
        )

    return records


def parse_old_json(json_path: Path) -> list[BookmarkRecord]:
    """Load the JSON shape exported by the original bookmarkchecker."""
    with json_path.open("r", encoding="utf-8") as fp:
        raw = json.load(fp)

    records: list[BookmarkRecord] = []
    for key, item in raw.items():
        add_date = item.get("add_date") or {}
        try:
            idx = int(key)
        except ValueError:
            idx = len(records)

        records.append(
            BookmarkRecord(
                id=idx,
                title=item.get("title", ""),
                url=item.get("url", ""),
                add_date_epoch=str(add_date.get("epoch", "")),
                add_date_localtime=str(add_date.get("localtime", "")),
            )
        )

    return records


def method_sequence(method_mode: str) -> list[str]:
    if method_mode == "head":
        return ["HEAD"]
    if method_mode == "head-get":
        return ["HEAD", "GET"]
    return ["GET"]


def classify_http_status(status: int | None) -> tuple[str, bool]:
    """
    Returns (live_state, server_responded).

    server_responded means we got a real HTTP response, even if the page is forbidden,
    missing, or server-erroring. This is different from whether the bookmark is useful.
    """
    if status is None:
        return "unknown", False

    if 200 <= status <= 299:
        return "live", True
    if 300 <= status <= 399:
        return "redirect_unresolved", True
    if status in {401, 403, 407, 409, 418, 429, 451, 460}:
        return "alive_blocked_or_rate_limited", True
    if status in {404, 410}:
        return "missing", True
    if 500 <= status <= 599:
        return "server_error", True
    return "http_other", True


def classify_exception(exc: BaseException) -> str:
    name = type(exc).__name__

    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, aiohttp.InvalidURL):
        return "invalid_url"
    if isinstance(exc, aiohttp.TooManyRedirects):
        return "too_many_redirects"
    if isinstance(exc, aiohttp.ClientSSLError) or "SSL" in name or "Certificate" in name:
        return "ssl_error"
    if isinstance(exc, aiohttp.ClientConnectorError):
        os_error = getattr(exc, "os_error", None)
        if isinstance(os_error, socket.gaierror):
            return "dns_error"
        if isinstance(os_error, ConnectionRefusedError):
            return "connection_refused"
        return "connection_error"
    if isinstance(exc, aiohttp.ClientPayloadError):
        return "payload_error"
    if isinstance(exc, aiohttp.ClientResponseError):
        return "response_error"
    if isinstance(exc, aiohttp.ClientError):
        return "client_error"
    if isinstance(exc, ssl.SSLError):
        return "ssl_error"

    return name


def exception_live_state(error_type: str) -> str:
    mapping = {
        "timeout": "timeout_unknown",
        "dns_error": "dns_failed",
        "ssl_error": "ssl_failed",
        "connection_refused": "connection_refused",
        "connection_error": "connection_failed",
        "invalid_url": "invalid_url",
        "too_many_redirects": "too_many_redirects",
    }
    return mapping.get(error_type, "request_failed")


def should_retry(error_type: str) -> bool:
    return error_type in {
        "timeout",
        "connection_error",
        "connection_refused",
        "payload_error",
        "client_error",
        "response_error",
    }


async def request_once(
    session: aiohttp.ClientSession,
    record: BookmarkRecord,
    method: str,
    timeout_seconds: float,
    ssl_verify: bool,
) -> BookmarkRecord:
    start = time.perf_counter()
    timeout = aiohttp.ClientTimeout(
        total=timeout_seconds,
        connect=min(15, timeout_seconds),
        sock_connect=min(15, timeout_seconds),
        sock_read=timeout_seconds,
    )

    try:
        async with session.request(
            method,
            record.url,
            allow_redirects=True,
            max_redirects=10,
            timeout=timeout,
            ssl=ssl_verify,
        ) as response:
            # For GET, read only a tiny amount. We are checking reachability, not mirroring pages.
            if method == "GET":
                try:
                    await response.content.read(1024)
                except Exception:
                    # The HTTP status still matters even if payload reading is weird.
                    pass

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            live_state, server_responded = classify_http_status(response.status)
            redirect_chain = " > ".join(str(r.status) for r in response.history)
            if redirect_chain:
                redirect_chain = f"{redirect_chain} > {response.status}"
            else:
                redirect_chain = str(response.status)

            record.method = method
            record.resp_code = response.status
            record.live_state = live_state
            record.server_responded = server_responded
            record.final_url = str(response.url)
            record.redirect_chain = redirect_chain
            record.content_type = response.headers.get("Content-Type", "")
            record.content_length = response.headers.get("Content-Length", "")
            record.elapsed_ms = elapsed_ms
            record.error_type = ""
            record.exception = ""
            return record

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        error_type = classify_exception(exc)
        record.method = method
        record.resp_code = None
        record.live_state = exception_live_state(error_type)
        record.server_responded = False
        record.final_url = ""
        record.redirect_chain = ""
        record.content_type = ""
        record.content_length = ""
        record.elapsed_ms = elapsed_ms
        record.error_type = error_type
        record.exception = repr(exc)
        return record


async def check_one(
    session: aiohttp.ClientSession,
    record: BookmarkRecord,
    semaphore: asyncio.Semaphore,
    method_mode: str,
    timeout_seconds: float,
    retries: int,
    ssl_fallback: bool,
) -> BookmarkRecord:
    parsed = urlparse(record.url)
    if parsed.scheme not in {"http", "https"}:
        record.live_state = "skipped_non_web_url"
        record.notes = f"scheme={parsed.scheme or 'missing'}"
        return record

    async with semaphore:
        last_result = record
        methods = method_sequence(method_mode)

        for attempt in range(retries + 1):
            for method in methods:
                candidate = BookmarkRecord(**asdict(record))
                candidate.attempts = attempt + 1
                result = await request_once(
                    session=session,
                    record=candidate,
                    method=method,
                    timeout_seconds=timeout_seconds,
                    ssl_verify=True,
                )

                # HEAD is often blocked or not supported. In head-get mode, let GET try next.
                if method == "HEAD" and method_mode == "head-get" and result.resp_code in {403, 405, 406, 501}:
                    last_result = result
                    continue

                # Optional SSL fallback: useful for old bookmarks with bad cert chains.
                # We preserve the warning so you know verification failed.
                if result.error_type == "ssl_error" and ssl_fallback:
                    fallback = BookmarkRecord(**asdict(record))
                    fallback.attempts = attempt + 1
                    fallback = await request_once(
                        session=session,
                        record=fallback,
                        method=method,
                        timeout_seconds=timeout_seconds,
                        ssl_verify=False,
                    )
                    fallback.notes = "ssl verification failed; retried with ssl=False"
                    result = fallback

                last_result = result

                # If the server answered, do not retry. A 403/404/503 is a real output.
                if result.server_responded:
                    return result

                # If failure is not likely transient, do not keep hammering.
                if not should_retry(result.error_type):
                    return result

            if attempt < retries:
                await asyncio.sleep(0.5 * (2**attempt))

        return last_result


async def check_records(
    records: list[BookmarkRecord],
    concurrency: int,
    timeout_seconds: float,
    retries: int,
    method_mode: str,
    user_agent: str,
    ssl_fallback: bool,
) -> list[BookmarkRecord]:
    headers = dict(DEFAULT_HEADERS)
    headers["User-Agent"] = user_agent

    connector = aiohttp.TCPConnector(
        limit=max(concurrency, 1),
        limit_per_host=max(min(concurrency, 5), 1),
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )

    semaphore = asyncio.Semaphore(max(concurrency, 1))

    async with aiohttp.ClientSession(headers=headers, connector=connector, trust_env=True) as session:
        tasks = [
            check_one(
                session=session,
                record=record,
                semaphore=semaphore,
                method_mode=method_mode,
                timeout_seconds=timeout_seconds,
                retries=retries,
                ssl_fallback=ssl_fallback,
            )
            for record in records
        ]

        results: list[BookmarkRecord] = []
        total = len(tasks)
        completed = 0
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"Checked {completed}/{total}...")

    return sorted(results, key=lambda r: r.id)


def write_csv(records: Iterable[BookmarkRecord], output_path: Path) -> None:
    rows = [asdict(record) for record in records]
    fieldnames = list(asdict(BookmarkRecord(id=0, title="", url="")).keys())

    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(records: Iterable[BookmarkRecord], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump([asdict(record) for record in records], fp, indent=2, ensure_ascii=False)


def print_summary(records: list[BookmarkRecord]) -> None:
    print("\nSummary")
    print("=======")
    print(f"Total records: {len(records)}")

    print("\nLive states:")
    for state, count in Counter(r.live_state for r in records).most_common():
        print(f"  {state}: {count}")

    print("\nHTTP response codes:")
    code_counts = Counter(str(r.resp_code) if r.resp_code is not None else "NO_HTTP_RESPONSE" for r in records)
    for code, count in code_counts.most_common():
        print(f"  {code}: {count}")

    error_counts = Counter(r.error_type for r in records if r.error_type)
    if error_counts:
        print("\nException types:")
        for error_type, count in error_counts.most_common():
            print(f"  {error_type}: {count}")


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description="Check browser bookmarks and export more realistic results.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-b", "--bookmark", type=Path, help="Chrome/Edge/Firefox exported bookmark HTML file")
    source.add_argument("-j", "--json", type=Path, help="Old bookmarkchecker JSON export")

    parser.add_argument("-o", "--output", type=Path, default=Path("bookmarkcheck_results.csv"), help="CSV output path")
    parser.add_argument("--json-output", type=Path, help="Optional JSON output path")
    parser.add_argument("--no-check", action="store_true", help="Only parse/export without checking URLs")
    parser.add_argument("--concurrency", type=positive_int, default=10, help="Concurrent URL checks; default: 10")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout per request in seconds; default: 30")
    parser.add_argument("--retries", type=int, default=1, help="Retries for transient failures; default: 1")
    parser.add_argument("--method", choices=["get", "head", "head-get"], default="get", help="Request method strategy; default: get")
    parser.add_argument("--ssl-fallback", action="store_true", help="If SSL verification fails, retry once with ssl=False and mark notes")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header to send")

    args = parser.parse_args()

    if args.bookmark:
        records = parse_bookmark_html(args.bookmark)
    else:
        records = parse_old_json(args.json)

    print(f"Loaded {len(records)} bookmarks.")

    if not args.no_check:
        records = asyncio.run(
            check_records(
                records=records,
                concurrency=args.concurrency,
                timeout_seconds=args.timeout,
                retries=max(args.retries, 0),
                method_mode=args.method,
                user_agent=args.user_agent,
                ssl_fallback=args.ssl_fallback,
            )
        )

    write_csv(records, args.output)
    print(f"Wrote CSV: {args.output}")

    if args.json_output:
        write_json(records, args.json_output)
        print(f"Wrote JSON: {args.json_output}")

    print_summary(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
