"""What chat's reactions say happened, for the gaming profile.

Chat replay says more than how many people were talking (analysis/hype.py's
unique-chatter curve, which standard scoring keeps): a burst of messages far
above the stream's own rate marks a moment, and what they say marks what kind
of moment it was. A wall of POG / NO WAY is a big play, KEKW / LUL a funny
one, monkaS a scare, F / L a fail, "clip it" viewers asking for exactly this.
(Stream-highlight research and clip tools agree on both; docs/GAMING.md.)

Chat reacts after the moment, by the stream's delay plus typing time, so a
spike is dated config/gaming.yaml's chat_lag_seconds earlier. Everything is
measured against this stream's own chat, so a small channel's burst of
twelve messages counts like a big channel's burst of three hundred.
"""

import re
from dataclasses import dataclass, field

import numpy as np

WINDOW = 5            # seconds a burst is counted over
BASELINE = 180        # seconds of chat before the pre-burst gap that set the normal rate
BASELINE_GAP = 15     # gap before the burst so early reactions don't inflate the baseline
SPIKE = 3.0           # a burst this many times the normal rate is a moment
MIN_BURST = 4         # ...and at least this many unique-chatter messages
# A burst with no reaction in it (no emote or word a class knows) is weaker
# evidence, so it has to stand out more.
PLAIN_SPIKE = 4.0
PLAIN_MIN_BURST = 6
MIN_UNIQUE_RATIO = 0.55  # reject bursts dominated by spam / copypasta from a few accounts
MAX_EVENTS = 60
MERGE_SECONDS = 15    # bursts this close together are one moment

_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF]")


@dataclass
class ChatSignal:
    """curve: per second 0..1, how strongly chat marks a moment there (already
    moved earlier for chat's lag). events: (second, "CHAT: ...") for the model."""
    curve: np.ndarray
    events: list = field(default_factory=list)
    messages: int = 0
    event_meta: list = field(default_factory=list)


_TOKEN = re.compile(r"[\w+':?!]+")
_CHANNEL_EMOTE = re.compile(r"[a-z][a-z0-9]{1,24}([A-Z0-9][\w]*)")


def _matchers(classes: dict) -> dict:
    """Per class: exact whole-word tokens, phrases / emoji found anywhere,
    channel-emote suffixes and regular expressions (config/gaming.yaml)."""
    out = {}
    for key, spec in (classes or {}).items():
        tokens, phrases = set(), []
        for w in spec.get("words") or []:
            w = str(w)
            if " " in w or not re.fullmatch(r"[\w+':]+", w) or not w.isascii():
                phrases.append(w.lower())       # phrases, emoji and other scripts
            else:
                tokens.add(w)
        suffixes = {str(x) for x in spec.get("suffixes") or []}
        patterns = [re.compile(str(p), re.IGNORECASE) for p in spec.get("patterns") or []]
        whole = [re.compile(str(p), re.IGNORECASE) for p in spec.get("message_patterns") or []]
        out[key] = (tokens, phrases, spec.get("label", key), suffixes, patterns, whole)
    return out


def classify(text: str, matchers: dict) -> dict:
    """The classes one message belongs to, with the words that put it there."""
    found = {}
    tokens = set(_TOKEN.findall(text or ""))
    pieces = set((text or "").split()) | tokens
    low = (text or "").lower()
    emote_ends = {m.group(1): tok for tok in tokens if (m := _CHANNEL_EMOTE.fullmatch(tok))}
    message = (text or "").strip()
    for key, (words, phrases, _label, suffixes, patterns, whole) in matchers.items():
        hits = [w for w in words if w in tokens] + [p for p in phrases if p in low]
        hits += [tok for end, tok in emote_ends.items() if end in suffixes]
        hits += [p for p in pieces for rx in patterns if rx.search(p)][:3]
        hits += [message for rx in whole if rx.search(message)][:1]
        if hits:
            found[key] = hits
    return found


def _short(text: str) -> bool:
    """A reaction-length message (an emote, "www", "no way"), as opposed to
    someone writing a question or an opinion."""
    t = (text or "").strip()
    return len(t) <= 14 or len(t.split()) <= 3


def _only(text: str, ignore: set) -> bool:
    """A message made only of hellos / good lucks (config/gaming.yaml chat_ignore)."""
    low = (text or "").strip().lower()
    if not low:
        return False
    if low in ignore:
        return True
    words = re.findall(r"[\w']+", low)
    return bool(words) and all(w in ignore for w in words)


def _unpack_message(item) -> tuple[float, str, str, int]:
    """Normalize a chat item: 3-tuple, 4-tuple with emotes count, or dict."""
    if isinstance(item, dict):
        return (
            float(item.get("t", 0.0) or 0.0),
            str(item.get("user") or ""),
            str(item.get("text") or ""),
            int(item.get("emotes") or 0),
        )
    t = float(item[0])
    who = str(item[1] or "")
    text = str(item[2] or "")
    emotes = int(item[3]) if len(item) > 3 and item[3] is not None else 0
    return t, who, text, emotes


def chat_signal(messages: list, duration: float, classes: dict, lag: float = 6.0,
                ignore: list | None = None) -> ChatSignal | None:
    """messages: [(offset seconds, author, text)] or 4-tuples/dicts with optional
    `emotes`. None when there is too little chat to tell anything from (under one
    message a minute). `ignore`: words a message made only of isn't a reaction."""
    n = int(duration) + 1
    if n < WINDOW * 4 or not messages:
        return None
    if len(messages) < duration / 60:
        return None
    matchers = _matchers(classes)
    ignored = {str(w).lower() for w in (ignore or [])}
    rate = np.zeros(n, dtype=np.float32)
    short = np.zeros(n, dtype=np.float32)
    emote_msg = np.zeros(n, dtype=np.float32)
    per_class = {k: np.zeros(n, dtype=np.float32) for k in matchers}
    words_at: dict[int, dict] = {}
    authors_at: dict[int, list[str]] = {}
    last_by_who: dict[str, float] = {}

    for item in messages:
        t, who, text, em_cnt = _unpack_message(item)
        s = int(t)
        if not 0 <= s < n:
            continue
        found = classify(text, matchers)
        if not found and ignored and _only(text, ignored):
            continue                      # a hello isn't a reaction to anything
        if who:
            prev_t = last_by_who.get(who)
            if prev_t is not None and (t - prev_t) < WINDOW:
                continue                  # cap burst spam to 1 counted reaction per author/window
            last_by_who[who] = t
        rate[s] += 1
        authors_at.setdefault(s, []).append(who or f"_anon_{s}_{int(rate[s])}")
        if _short(text):
            short[s] += 1
        hit_count = sum(len(v) for v in found.values())
        if em_cnt > 0 or hit_count >= 2 or (hit_count >= 1 and len(text.strip()) <= 18) or _EMOJI_RE.search(text):
            emote_msg[s] += 1
        for key, hits in found.items():
            per_class[key][s] += 1
            bucket = words_at.setdefault(s, {})
            for h in hits:
                bucket[h] = bucket.get(h, 0) + 1

    idx = np.arange(n)

    def window_sum(x: np.ndarray, width: int) -> np.ndarray:
        """Messages in the `width` seconds ending at t: looking back only, so
        a burst is dated where it starts, not seconds before it."""
        c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
        return (c[idx + 1] - c[np.maximum(idx + 1 - width, 0)]).astype(np.float32)

    burst = window_sum(rate, WINDOW)                     # messages in (t-5, t]
    # Normal rate over BASELINE seconds ending BASELINE_GAP before the burst so
    # an early reaction ramp doesn't inflate the denominator. Floor adapts to
    # chat size so quiet channels keep sensitivity and busy channels resist chatter.
    before = np.concatenate([[0.0], np.cumsum(rate, dtype=np.float64)])
    hi = np.maximum(idx + 1 - WINDOW - BASELINE_GAP, 0)
    lo = np.maximum(hi - BASELINE, 0)
    span = np.maximum(hi - lo, 1)
    normal = ((before[hi] - before[lo]) / span * WINDOW).astype(np.float32)
    med = float(np.median(burst))
    global_rate = float(rate.sum() / max(duration, 1.0) * WINDOW)
    if global_rate < 1.5:
        floor = max(med, min(1.0, max(0.55, global_rate * 0.85)))
        eff_min = 3.0 if global_rate < 1.2 else float(MIN_BURST)
        eff_plain_min = 5.0 if global_rate < 1.2 else float(PLAIN_MIN_BURST)
    else:
        floor = max(med, global_rate * 0.70)
        eff_min = float(MIN_BURST)
        eff_plain_min = float(PLAIN_MIN_BURST)

    ratio = burst / np.maximum(normal, floor)
    reacting = sum(window_sum(v, WINDOW) for v in per_class.values())
    share = np.clip(reacting / np.maximum(burst, 1.0), 0.0, 1.0)
    brief = np.clip(window_sum(short, WINDOW) / np.maximum(burst, 1.0), 0.0, 1.0)
    em_share = np.clip(window_sum(emote_msg, WINDOW) / np.maximum(burst, 1.0), 0.0, 1.0)
    # 0 at the normal rate, saturates toward 1 at 2.5x SPIKE. What chat says
    # (reaction classes + emote bursts) and how concisely it says it scale strength.
    r_term = np.clip((ratio - 1.0) / (2.5 * SPIKE - 1.0), 0.0, 1.0)
    strength = r_term * (0.50 + 0.35 * share + 0.15 * em_share) * (0.5 + 0.5 * brief)

    shift = max(0, int(round(lag)))
    curve = np.zeros(n, dtype=np.float32)
    curve[: n - shift] = strength[shift:]

    # Events: where a burst starts, dated back by the lag, named by what chat said.
    events = []
    hot = (ratio >= SPIKE) & (burst >= eff_min)
    s = 0
    while s < n:
        if not hot[s]:
            s += 1
            continue
        e = s
        while e + 1 < n and hot[e + 1]:
            e += 1
        win_authors: list[str] = []
        for sec in range(max(0, s - WINDOW + 1), min(n, e + WINDOW)):
            win_authors.extend(authors_at.get(sec) or ())
        if win_authors and (len(set(win_authors)) / len(win_authors)) < MIN_UNIQUE_RATIO:
            s = e + 1
            continue
        counts: dict = {}
        klass: dict = {}
        for sec in range(s, min(e + WINDOW, n)):
            for w, c in (words_at.get(sec) or {}).items():
                counts[w] = counts.get(w, 0) + c
            for key in per_class:
                klass[key] = klass.get(key, 0) + int(per_class[key][sec])
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
        kind = max(klass, key=klass.get) if klass and max(klass.values()) > 0 else None
        if kind is None and (ratio[s:e + 1].max() < PLAIN_SPIKE or burst[s:e + 1].max() < eff_plain_min
                             or brief[s:e + 1].max() < 0.5):
            s = e + 1                     # chat talking, not reacting: not a moment
            continue
        label = matchers[kind][2] if kind else "a burst of messages"
        said = ", ".join(f"{w} x{c}" for w, c in top)
        text = f"CHAT: {label}" + (f" ({said})" if said else f" ({int(burst[s:e + 1].max())} messages in {WINDOW}s)")
        t_ev = max(0.0, float(s - shift))
        c_lo, c_hi = max(0, int(t_ev) - 2), min(n, int(t_ev) + 8)
        pk = float(curve[c_lo:c_hi].max()) if c_hi > c_lo else 0.0
        peak_ratio = float(ratio[s:e + 1].max())
        peak_em = float(em_share[s:e + 1].max())
        rank_score = pk * 0.6 + min(1.0, peak_ratio / 8.0) * 0.25 + peak_em * 0.15
        events.append((t_ev, text, rank_score, peak_ratio, [w for w, _c in top], kind or "burst", peak_em))
        s = e + 1
    # Bursts a few seconds apart are one moment chat kept reacting to: the
    # first names it, the strongest's words describe it.
    merged: list = []
    for ev in sorted(events, key=lambda ev: ev[0]):
        if merged and ev[0] - merged[-1][7] <= MERGE_SECONDS:
            first = merged[-1]
            best = ev if ev[2] > first[2] else first
            merged[-1] = (first[0], best[1], max(first[2], ev[2]), max(first[3], ev[3]), best[4], best[5], max(first[6], ev[6]), ev[0])
        else:
            merged.append((*ev, ev[0]))
    merged.sort(key=lambda ev: -ev[2])
    top_merged = sorted(merged[:MAX_EVENTS], key=lambda ev: ev[0])
    out_events = [(t, txt) for t, txt, *_ in top_merged]
    event_meta = [
        {
            "t": round(t, 2),
            "ratio": round(pk_ratio, 2),
            "score": round(rscore, 3),
            "words": top_w,
            "kind": knd,
            "emote_share": round(em_sh, 2),
        }
        for t, _txt, rscore, pk_ratio, top_w, knd, em_sh, _last in top_merged
    ]
    return ChatSignal(curve=curve, events=out_events, messages=len(messages), event_meta=event_meta)
