"""The "karaoke" and "pop" caption options, and the bundled Bebas Neue.

karaoke: the words already said keep the highlight colour, so a line fills
up as it is spoken (the CapCut look) instead of one word lighting at a time.
pop: the word being said grows and settles (100 -> 122 -> 112 %), only it.
Bebas Neue ships in assets/fonts and reaches libass through `fontsdir`.
"""

import re
import subprocess
from pathlib import Path

import pytest

from core.binaries import ffmpeg
from core.models import ClipCandidate, Segment
from video.captions import build_caption_lines, build_captions, caption_font_for, words_of
from video.filters import FONTS_DIR, subtitles_filter

GREEN = "&H14FF39&"  # #39FF14 as an inline ASS colour
CLIP = ClipCandidate(start=10.0, end=20.0, score=0)
LIT = {"highlight": True, "highlight_color": "#39FF14", "words_per_caption": 4}
POP = r"\t(0,70,\fscx122\fscy122)\t(70,150,\fscx112\fscy112)"


def _burn(tmp_path, style) -> list[str]:
    """The Text of each Dialogue, for a word every half second (W20 is at 10.0 s)."""
    words = [{"start": i * 0.5, "end": i * 0.5 + 0.5, "word": f"w{i}"} for i in range(120)]
    segs = [Segment(start=0.0, end=60.0, text=" ".join(w["word"] for w in words), words=words)]
    text = build_captions(segs, CLIP, tmp_path / "c.ass", style=style).read_text(encoding="utf-8")
    return [line.split(",,0,0,0,,", 1)[1] for line in text.splitlines() if line.startswith("Dialogue:")]


def _lit(event: str) -> list[str]:
    """The words of one event drawn in the highlight colour."""
    out, colour = [], None
    for m in re.finditer(r"\\1c(&H[0-9A-F]{6}&)|(W\d+)", event):
        if m[1]:
            colour = m[1]
        elif colour == GREEN:
            out.append(m[2])
    return out


def test_karaoke_keeps_the_words_already_said_lit(tmp_path):
    events = _burn(tmp_path, {**LIT, "karaoke": True})
    assert [_lit(e) for e in events[:5]] == [
        ["W20"], ["W20", "W21"], ["W20", "W21", "W22"], ["W20", "W21", "W22", "W23"], ["W24"]]


def test_without_karaoke_one_word_is_lit_at_a_time(tmp_path):
    events = _burn(tmp_path, LIT)
    assert [_lit(e) for e in events[:4]] == [["W20"], ["W21"], ["W22"], ["W23"]]
    assert not any("fscx" in e for e in events)  # no pop unless asked for


def test_pop_grows_only_the_word_being_said(tmp_path):
    events = _burn(tmp_path, {**LIT, "pop": True})
    for k, event in enumerate(events[:4]):
        assert event.count(r"\t(") == 2
        popped = re.search(re.escape(POP) + r"[^}]*\}(W\d+)\{\\fscx100\\fscy100", event)
        assert popped and popped[1] == f"W{20 + k}"


def test_hyphenated_words_share_one_caption_slot_and_animation(tmp_path):
    fragments = "dê -me faça -se guarda- chuva anti -herói. próximo".split()
    words = [{"start": 10 + i / 2, "end": 10.5 + i / 2, "word": word}
             for i, word in enumerate(fragments)]
    segs = [Segment(start=10, end=14.5, text="dê-me faça-se guarda-chuva anti-herói. próximo", words=words)]

    assert build_caption_lines(segs, CLIP, 4) == [
        {"start": 0.0, "end": 4.0, "text": "dê-me faça-se guarda-chuva anti-herói."},
        {"start": 4.0, "end": 4.5, "text": "próximo"},
    ]
    assert words_of(segs, CLIP)[0] == {"start": 0.0, "end": 1.0, "word": "dê-me"}
    path = build_captions(segs, CLIP, tmp_path / "hifen.ass", style={**LIT, "karaoke": True, "pop": True})
    events = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 5
    assert events[0].startswith("Dialogue: 0,0:00:00.00,0:00:01.00,")
    assert re.sub(r"\{[^}]*\}", "", events[0]).endswith("DÊ-ME FAÇA-SE GUARDA-CHUVA ANTI-HERÓI.")


def test_separate_caption_dashes_are_preserved():
    tokens = ["ele", "-", "sim", "para", "—", "agora", "menos", "-10"]
    words = [{"start": 10 + i / 2, "end": 10.5 + i / 2, "word": word}
             for i, word in enumerate(tokens)]
    segs = [Segment(start=10, end=14, text=" ".join(tokens), words=words)]

    assert [line["text"] for line in build_caption_lines(segs, CLIP, 4)] == [
        "ele - sim para", "— agora menos -10",
    ]


def test_bebas_neue_is_a_caption_font_and_may_go_past_140(tmp_path):
    words = [{"start": 10.0, "end": 10.5, "word": "ola"}]
    path = build_captions([Segment(start=0.0, end=60.0, text="ola", words=words)], CLIP,
                          tmp_path / "c.ass", style={"font": "Bebas Neue", "font_size": 165})
    assert "Style: Default,Bebas Neue,165," in path.read_text(encoding="utf-8")


def test_bebas_neue_gives_way_to_a_script_font():
    assert caption_font_for("ja", "Bebas Neue") == "Yu Gothic UI"  # it has no Japanese glyphs
    assert caption_font_for("pt", "Bebas Neue") == "Bebas Neue"


def test_the_filter_points_libass_at_the_bundled_fonts():
    assert (FONTS_DIR / "BebasNeue-Regular.ttf").is_file()
    assert subtitles_filter("c.ass") == "subtitles=c.ass:fontsdir=" + FONTS_DIR.as_posix().replace(":", r"\\:")


def test_ffmpeg_burns_with_the_bundled_font(tmp_path):
    binary = ffmpeg()
    if not Path(binary).is_file():
        pytest.skip("FFmpeg is not installed here")
    words = [{"start": 10.0, "end": 10.8, "word": "ola"}]
    build_captions([Segment(start=0.0, end=60.0, text="ola", words=words)], CLIP,
                   tmp_path / "c.ass", style={"font": "Bebas Neue"})
    result = subprocess.run(
        [binary, "-v", "verbose", "-f", "lavfi", "-i", "color=black:s=1080x1920:d=1",
         "-vf", subtitles_filter("c.ass"), "-f", "null", "-"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert re.search(r"fontselect: \(Bebas Neue.*-> BebasNeue", result.stderr), result.stderr[-800:]
