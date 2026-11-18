"""Name screening against the US Restricted Parties feed (pure functions, no Apify imports).

The feed is https://github.com/Mattbusel/us-restricted-parties (CC BY 4.0, compiled by Tensorust LLC from
US government sources): DoD 1260H with named subsidiaries, Section 889, the FCC Covered List, the DHS UFLPA
Entity List and the interim BIOSECURE list, as Senzing JSON Lines. Matching follows that repo's
tools/check_names.py: normalize both names (ASCII fold, lowercase, drop punctuation and legal suffixes),
score 1.0 for an exact normalized match, otherwise difflib's ratio, and keep the best scores at or above
the floor. One addition: a distinctive name found whole inside a listed name ("Hikvision" in "Hangzhou
Hikvision Digital Technology Company") scores CONTAINED (0.9), because several official listings carry only
the long legal name.
"""
from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

FEED_URL = "https://github.com/Mattbusel/us-restricted-parties/releases/latest/download/all.jsonl"
MANIFEST_URL = "https://github.com/Mattbusel/us-restricted-parties/releases/latest/download/manifest.json"

LISTS = {
    "US_DOD_1260H": "DoD Chinese Military Companies (Section 1260H)",
    "US_FAR_889": "Section 889 covered telecommunications and video surveillance companies",
    "US_FCC_COVERED": "FCC Covered List",
    "US_DHS_UFLPA": "UFLPA Entity List",
    "US_BIOSECURE": "BIOSECURE biotechnology companies of concern (interim)",
}

CONTAINED = 0.9
# Words that never make a contained match on their own ("Technology" must not hit every listed tech company).
_GENERIC = set("""
china chinese technology technologies tech digital international industrial industry industries electronics electronic
electric trading trade science sciences scientific development engineering construction materials energy power systems
system communications communication network networks equipment manufacturing research institute university academy
investment capital bio biotech pharmaceutical pharma medical health new national state hong kong shenzhen beijing
shanghai xinjiang hangzhou guangzhou zhejiang jiangsu shandong textile textiles cotton import export logistics shipping
group company corporation limited holdings aviation aerospace semiconductor semiconductors mobile telecom optical
marine heavy machinery automotive motor motors chemical chemicals agricultural food foods solar battery steel metal metals
mining aircraft satellite space shipbuilding nuclear security software information
""".split())

_SUFFIX = re.compile(r"\b(co|company|corp|corporation|inc|incorporated|ltd|limited|llc|plc|group|holdings?|the|of|and)\b")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", s)).strip()


@dataclass
class Record:
    raw: dict
    names: list[tuple[str, str]] = field(default_factory=list)  # (as listed, normalized)


def parse_feed(lines: Iterable[str], lists: Iterable[str] | None = None) -> list[Record]:
    keep = set(lists) if lists else None
    out: list[Record] = []
    for line in lines:
        if not line.strip():
            continue
        r = json.loads(line)
        if keep is not None and r.get("DATA_SOURCE") not in keep:
            continue
        names = {r["NAME_ORG"]} | {n["NAME_ORG"] for n in r.get("NAMES", []) if n.get("NAME_ORG")}
        pairs = sorted((n, norm(n)) for n in names if norm(n))
        out.append(Record(r, pairs))
    return out


def screen(name: str, records: list[Record], floor: float = 0.88, limit: int = 3) -> list[dict]:
    """Best matches for one name, highest score first. A match is a lead to check against the source."""
    q = norm(name)
    if not q:
        return []
    distinctive = len(q) >= 5 and not all(w in _GENERIC for w in q.split())
    hits = []
    for rec in records:
        score, via, kind = 0.0, "", ""
        for raw, n in rec.names:
            if n == q:
                s, k = 1.0, "exact"
            else:
                s, k = difflib.SequenceMatcher(None, q, n).ratio(), "similar"
                if s < CONTAINED and distinctive and f" {q} " in f" {n} ":
                    s, k = CONTAINED, "contained"
            if s > score:
                score, via, kind = s, raw, k
        if score >= floor:
            r = rec.raw
            hits.append({
                "score": round(score, 3),
                "matchType": kind,
                "list": r.get("LIST_NAME"),
                "dataSource": r.get("DATA_SOURCE"),
                "listedName": r.get("NAME_ORG"),
                "matchedName": via,
                "parentName": r.get("PARENT_NAME"),
                "listedOn": r.get("LISTED_ON"),
                "includesAffiliates": bool(r.get("INCLUDES_AFFILIATES", False)),
                "sourceUrl": r.get("SOURCE_URL"),
                "sourceDoc": r.get("SOURCE_DOC"),
                "recordId": r.get("RECORD_ID"),
            })
    hits.sort(key=lambda h: (-h["score"], h["recordId"] or ""))
    return hits[:limit]


def result_item(name: str, hits: list[dict], feed: dict) -> dict:
    return {
        "input": name,
        "normalized": norm(name),
        "hit": bool(hits),
        "bestScore": hits[0]["score"] if hits else None,
        "matches": hits,
        "feedRelease": feed.get("release"),
        "feedBuiltAt": feed.get("builtAt"),
        "note": "A match is a lead to review against the government source URL, not a legal finding. "
        "A name with no match is not a clearance: some listings cover unnamed affiliates (includesAffiliates).",
    }


def clean_names(names: Iterable[object], max_names: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if not isinstance(n, str):
            continue
        s = " ".join(n.split())
        if s and s not in seen:
            seen.add(s)
            out.append(s)
        if len(out) >= max_names:
            break
    return out
