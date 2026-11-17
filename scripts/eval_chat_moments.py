"""Collect and evaluate real Twitch GTA V / GTA RP chat-moment benchmarks.

Usage:
  python scripts/eval_chat_moments.py --collect   # fetches Helix + VOD replay chat -> fixture
  python scripts/eval_chat_moments.py             # runs tune / val evaluation on the saved fixture

Credentials for --collect are read from ../cola/.env (never logged or saved into the fixture).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "twitch_gta_chat_moments.json"
ENV_PATH = ROOT.parent / "cola" / ".env"


def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _helix_client(env: dict[str, str]):
    cid = env["TWITCH_CLIENT_ID"]
    sec = env["TWITCH_CLIENT_SECRET"]
    req = urllib.request.Request(
        "https://id.twitch.tv/oauth2/token",
        data=urllib.parse.urlencode(
            {"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}
        ).encode(),
        method="POST",
    )
    token = json.loads(urllib.request.urlopen(req, timeout=20).read())["access_token"]
    headers = {"Client-Id": cid, "Authorization": f"Bearer {token}"}

    def get(path: str, params) -> dict:
        url = "https://api.twitch.tv/helix" + path + "?" + urllib.parse.urlencode(params, doseq=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
            return json.load(resp)

    return get


def _parse_twitch_duration(text: str) -> float:
    import re

    total = 0.0
    for val, unit in re.findall(r"(\d+)([hms])", text or ""):
        n = int(val)
        total += n * (3600 if unit == "h" else 60 if unit == "m" else 1)
    return total


def _hash_author(raw_id: str) -> str:
    return hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:10]


def _fetch_vod_chat_window(vod_id: str, win_start: float, win_end: float, client_id: str) -> list[list]:
    """Reuse analysis/hype.py's GQL query + Client-ID to fetch chat inside [win_start, win_end]."""
    from analysis.hype import _COMMENTS_QUERY, _GQL_URL, _UA

    seen: set[tuple[float, str, str]] = set()
    offset = max(0.0, float(int(win_start)))
    deadline = time.monotonic() + 60.0
    for _ in range(250):
        body = json.dumps(
            {"query": _COMMENTS_QUERY, "variables": {"videoID": vod_id, "offset": int(offset)}}
        ).encode()
        req = urllib.request.Request(
            _GQL_URL,
            data=body,
            headers={
                "Client-ID": client_id,
                "Content-Type": "application/json",
                "User-Agent": _UA,
            },
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        video = (data.get("data") or {}).get("video")
        if not video or not video.get("comments"):
            break
        edges = video["comments"]["edges"]
        if not edges:
            break
        last = 0.0
        for e in edges:
            node = e["node"]
            t = float(node["contentOffsetSeconds"])
            last = max(last, t)
            commenter = node.get("commenter") or {}
            if commenter.get("id") and win_start <= t <= win_end:
                fragments = (node.get("message") or {}).get("fragments") or []
                text = "".join(str(f.get("text") or "") for f in fragments)
                seen.add((round(t - win_start, 2), _hash_author(str(commenter["id"])), text))
        if last >= win_end or last < offset + 1:
            break
        offset = last + 1
        if time.monotonic() > deadline:
            break
    return [[t, who, text] for t, who, text in sorted(seen)]


def _best_window(clips: list[dict], vod_duration: float, target_span: float = 3000.0) -> tuple[float, float, list[dict]]:
    """Find a 50-minute (<=60m) VOD window maximizing included popular clips."""
    ordered = sorted(clips, key=lambda c: float(c["vod_offset"]))
    best: tuple[int, int, float, float, list[dict]] | None = None
    for i, first in enumerate(ordered):
        lo = max(0.0, float(first["vod_offset"]) - 240.0)
        hi = min(vod_duration, lo + target_span)
        if hi - lo < 1800.0:
            lo = max(0.0, hi - target_span)
        inside = [
            c for c in ordered[i:]
            if lo + 60.0 <= float(c["vod_offset"]) and float(c["vod_offset"]) + float(c.get("duration") or 30.0) <= hi - 60.0
        ]
        if not inside:
            continue
        score = (len(inside), sum(int(c.get("view_count") or 0) for c in inside))
        if best is None or score > best[:2]:
            best = (*score, lo, hi, inside)
    assert best is not None
    return best[2], best[3], best[4]


def collect_dataset(max_vods: int = 16) -> dict:
    from analysis.hype import _scrape_client_id

    env = _load_env(ENV_PATH)
    helix = _helix_client(env)
    gql_client_id = _scrape_client_id()
    games = helix("/games", [("name", "Grand Theft Auto V"), ("name", "Grand Theft Auto VI")])["data"]
    gta_ids = {g["id"] for g in games}
    since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")

    clips_by_vod: dict[str, list[dict]] = defaultdict(list)
    # 1. Global top clips across GTA V / GTA VI
    for g in games:
        cursor = None
        for _ in range(5):
            params = {"game_id": g["id"], "started_at": since, "first": 100}
            if cursor:
                params["after"] = cursor
            res = helix("/clips", params)
            for c in res.get("data", []):
                if c.get("video_id") and c.get("vod_offset") is not None:
                    clips_by_vod[c["video_id"]].append(c)
            cursor = (res.get("pagination") or {}).get("cursor")
            if not cursor:
                break

    # 2. Also sample PT and EN live GTA V broadcasters so Portuguese & English chats are well represented
    for lang in ("pt", "en"):
        streams = helix("/streams", {"game_id": "32982", "language": lang, "first": 25}).get("data", [])
        for s in streams[:15]:
            res = helix("/clips", {"broadcaster_id": s["user_id"], "started_at": since, "first": 40})
            for c in res.get("data", []):
                if c.get("game_id") in gta_ids and c.get("video_id") and c.get("vod_offset") is not None:
                    clips_by_vod[c["video_id"]].append(c)

    # Deduplicate clip IDs per VOD
    for vid in list(clips_by_vod):
        dedup = {c["id"]: c for c in clips_by_vod[vid]}
        clips_by_vod[vid] = list(dedup.values())

    # Verify VODs exist on Helix
    vod_meta: dict[str, dict] = {}
    vids = list(clips_by_vod.keys())
    for i in range(0, len(vids), 100):
        for v in helix("/videos", [("id", v) for v in vids[i : i + 100]]).get("data", []):
            vod_meta[v["id"]] = v

    # Pick diverse VODs across pt, en, and other languages with >=3 clips in a 50-min window
    candidates: list[tuple[str, dict, float, float, list[dict]]] = []
    for vid, cs in clips_by_vod.items():
        v = vod_meta.get(vid)
        if not v:
            continue
        dur = _parse_twitch_duration(v.get("duration", ""))
        if dur < 1800:
            continue
        lo, hi, inside = _best_window(cs, dur)
        if len(inside) >= 3:
            candidates.append((vid, v, lo, hi, inside))

    by_lang: dict[str, list] = defaultdict(list)
    for item in candidates:
        lang = (item[1].get("language") or "other").lower()
        bucket = lang if lang in ("pt", "en") else "other"
        by_lang[bucket].append(item)
    for bucket in by_lang.values():
        bucket.sort(key=lambda x: (len(x[4]), sum(c["view_count"] for c in x[4])), reverse=True)

    # Deduplicate same broadcaster in top picks when alternatives exist (keep up to 2 VODs per broadcaster)
    chosen: list = []
    seen_users: dict[str, int] = defaultdict(int)
    for bucket, quota in (("pt", 5), ("en", 6), ("other", 5)):
        taken = 0
        for item in by_lang.get(bucket, []):
            user = item[1].get("user_name") or ""
            if seen_users[user] >= 2:
                continue
            chosen.append(item)
            seen_users[user] += 1
            taken += 1
            if taken >= quota or len(chosen) >= max_vods:
                break

    samples = []
    for idx, (vid, v, lo, hi, inside) in enumerate(chosen):
        msgs = _fetch_vod_chat_window(vid, lo, hi, gql_client_id)
        dur_win = round(hi - lo, 1)
        if len(msgs) < dur_win / 30:  # skip dead/broken replay fetches
            print(f"  skip vod={vid} ({v.get('user_name')}): too few msgs ({len(msgs)})")
            continue
        clip_rows = []
        for c in sorted(inside, key=lambda x: float(x["vod_offset"])):
            clip_rows.append(
                {
                    "offset": round(float(c["vod_offset"]) - lo, 1),
                    "duration": round(float(c.get("duration") or 30.0), 1),
                    "views": int(c.get("view_count") or 0),
                }
            )
        samples.append(
            {
                "id": f"vod_{len(samples) + 1:02d}",
                "language": (v.get("language") or "other").lower(),
                "channel": v.get("user_name") or "",
                "window_duration": dur_win,
                "clips": clip_rows,
                "messages": msgs,
            }
        )
        print(
            f"  collected {samples[-1]['id']} [{samples[-1]['language']}] "
            f"{samples[-1]['channel']}: {dur_win:.0f}s, {len(clip_rows)} clips, {len(msgs)} msgs"
        )

    # Deterministic stratified split (tune vs held-out val) by language & order
    counters: dict[str, int] = defaultdict(int)
    for s in samples:
        lang = s["language"]
        s["split"] = "tune" if counters[lang] % 2 == 0 else "val"
        counters[lang] += 1

    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Twitch Helix /clips + VOD GQL chat replay (author IDs hashed)",
        "samples": samples,
    }
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(samples)} VOD windows to {FIXTURE_PATH}")
    return payload


def _cluster_clips(clips: list[dict], gap: float = 20.0) -> list[tuple[float, float, int]]:
    """Merge overlapping/adjacent clips of the same highlight into ground-truth intervals."""
    out: list[list] = []
    for c in sorted(clips, key=lambda x: x["offset"]):
        s, e, v = float(c["offset"]), float(c["offset"]) + float(c["duration"]), int(c["views"])
        if out and s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
            out[-1][2] += v
        else:
            out.append([s, e, v])
    return [(s, e, v) for s, e, v in out]


def _match_interval(t: float, gt: tuple[float, float, int], margin: float = 10.0) -> bool:
    return (gt[0] - margin) <= t <= (gt[1] + margin)


def evaluate(dataset: dict, lag: float = 6.0, k_list: tuple[int, ...] = (5, 10, 15)) -> dict:
    from analysis import gaming
    from analysis.chat_moments import chat_signal

    k = gaming.knowledge()
    classes = k["chat_classes"]
    ignore = k.get("chat_ignore") or []

    by_split: dict[str, dict] = {}
    for split in ("tune", "val", "all"):
        rows = [s for s in dataset["samples"] if split == "all" or s.get("split") == split]
        total_gt = 0
        hits_all = 0
        hits_k = {kk: 0 for kk in k_list}
        matched_det = 0
        total_det = 0
        abs_errors: list[float] = []
        signed_to_end: list[float] = []
        signed_to_mid: list[float] = []

        for s in rows:
            msgs = [(float(m[0]), str(m[1]), str(m[2])) for m in s["messages"]]
            dur = float(s["window_duration"])
            sig = chat_signal(msgs, dur, classes, lag=lag, ignore=ignore)
            gts = _cluster_clips(s["clips"])
            total_gt += len(gts)
            events = sig.events if sig is not None else []
            meta_by_t = (
                {round(float(m["t"]), 2): float(m["score"]) for m in (getattr(sig, "event_meta", None) or [])}
                if sig is not None else {}
            )
            # Rank events by integrated moment strength (curve peak + ratio + emotes)
            ranked = []
            for t, desc in events:
                if round(float(t), 2) in meta_by_t:
                    strength = meta_by_t[round(float(t), 2)]
                elif sig is not None and sig.curve.size:
                    lo = max(0, int(t) - 2)
                    hi = min(sig.curve.size, int(t) + 8)
                    strength = float(sig.curve[lo:hi].max()) if hi > lo else 0.0
                else:
                    strength = 0.0
                ranked.append((strength, t, desc))
            ranked.sort(key=lambda x: -x[0])

            total_det += len(ranked)
            for _str, t, _desc in ranked:
                if any(_match_interval(t, gt) for gt in gts):
                    matched_det += 1

            for gt in gts:
                mid = (gt[0] + gt[1]) / 2.0
                if any(_match_interval(t, gt) for _s, t, _d in ranked):
                    hits_all += 1
                    best_t = min(
                        (t for _s, t, _d in ranked if _match_interval(t, gt)),
                        key=lambda t: abs(t - mid),
                    )
                    abs_errors.append(abs(best_t - mid))
                    signed_to_end.append(best_t - gt[1])
                    signed_to_mid.append(best_t - mid)
                for kk in k_list:
                    if any(_match_interval(t, gt) for _s, t, _d in ranked[:kk]):
                        hits_k[kk] += 1

        recall_all = hits_all / max(1, total_gt)
        prec = matched_det / max(1, total_det)
        f1 = (2 * recall_all * prec / (recall_all + prec)) if (recall_all + prec) > 0 else 0.0
        by_split[split] = {
            "vods": len(rows),
            "gt_moments": total_gt,
            "detected": total_det,
            "precision": round(prec, 4),
            "recall_all": round(recall_all, 4),
            "f1": round(f1, 4),
            **{f"recall@{kk}": round(hits_k[kk] / max(1, total_gt), 4) for kk in k_list},
            "median_abs_err_s": round(statistics.median(abs_errors), 2) if abs_errors else None,
            "median_offset_to_mid_s": round(statistics.median(signed_to_mid), 2) if signed_to_mid else None,
            "median_offset_to_end_s": round(statistics.median(signed_to_end), 2) if signed_to_end else None,
        }
    return by_split


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="Collect Twitch Helix + VOD chat fixture")
    ap.add_argument("--lag", type=float, default=6.0, help="Chat lag seconds for replay eval")
    args = ap.parse_args()
    if args.collect:
        collect_dataset()
    dataset = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    res = evaluate(dataset, lag=args.lag)
    for split, metrics in res.items():
        print(f"[{split}] {metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
