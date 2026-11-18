"""Apify Actor: screen company names against five US restricted-party lists.

Input (see .actor/input_schema.json): names, minScore, lists, maxMatchesPerName.
Output: one dataset item per unique input name (the billed unit under pay-per-event), and an OUTPUT record
in the key-value store with totals and the feed release used.
"""
from __future__ import annotations

import json
import urllib.request

from apify import Actor

from .screen import FEED_URL, LISTS, MANIFEST_URL, clean_names, parse_feed, result_item, screen

MAX_NAMES = 50_000
UA = {"User-Agent": "apify-restricted-party-screen/0.1 (+https://github.com/Mattbusel/apify-restricted-party-screen)"}


class _Trail(urllib.request.HTTPRedirectHandler):
    """Keeps every redirect target: GitHub sends latest/download to releases/download/<tag>/ before the CDN."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.urls.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str) -> tuple[str, list[str]]:
    """Body, and the URLs the request was redirected through."""
    trail = _Trail()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.build_opener(trail).open(req, timeout=60) as r:
        return r.read().decode("utf-8"), trail.urls + [r.geturl()]


def release_tag(urls: list[str]) -> str | None:
    for u in urls:
        parts = u.split("/releases/download/")
        if len(parts) == 2:
            return parts[1].split("/")[0]
    return None


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        names = clean_names(inp.get("names") or [], MAX_NAMES)
        if not names:
            await Actor.fail(status_message='No names given. Put company names in the "names" input, one per line.')
            return
        floor = float(inp.get("minScore", 0.88))
        if not 0.5 <= floor <= 1.0:
            await Actor.fail(status_message=f"minScore must be between 0.5 and 1.0, got {floor}.")
            return
        limit = int(inp.get("maxMatchesPerName", 3))
        lists = [x for x in (inp.get("lists") or list(LISTS)) if x in LISTS] or list(LISTS)

        await Actor.set_status_message("Downloading the US Restricted Parties feed")
        body, trail = fetch(FEED_URL)
        try:
            manifest = json.loads(fetch(MANIFEST_URL)[0])
        except Exception as e:  # the feed itself is enough to screen; the manifest only adds provenance
            Actor.log.warning(f"manifest.json not read: {e}")
            manifest = {}
        feed = {"release": release_tag(trail), "builtAt": manifest.get("built_at")}
        records = parse_feed(body.splitlines(), lists)
        Actor.log.info(f"Feed {feed['release']} built {feed['builtAt']}: {len(records)} records on {', '.join(lists)}")

        n_hit = 0
        batch: list[dict] = []
        for i, name in enumerate(names, 1):
            item = result_item(name, screen(name, records, floor, limit), feed)
            n_hit += item["hit"]
            batch.append(item)
            if len(batch) == 500 or i == len(names):
                await Actor.push_data(batch)
                batch = []
                await Actor.set_status_message(f"Screened {i} of {len(names)} names, {n_hit} with a match")

        await Actor.set_value("OUTPUT", {
            "namesScreened": len(names),
            "namesWithMatch": n_hit,
            "minScore": floor,
            "lists": lists,
            "recordsLoaded": len(records),
            "feed": feed,
            "feedUrl": FEED_URL,
            "dataLicense": "CC BY 4.0. Data: US Restricted Parties by Tensorust LLC, https://github.com/Mattbusel/us-restricted-parties",
        })
