"""The Mesa's caption adjuster: saving applies to the next clip, with no restart.

The style lives in app_state and in the live config the worker copies per job,
so a restart keeps it and a running engine uses it at once.
"""

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _app(tmp_path):
    pytest.importorskip("fastapi")
    from main import BUNDLED_CONFIG, load_config
    from server.api import create_app

    settings = tmp_path / "settings.yaml"
    shutil.copy(ROOT / "config" / "settings.yaml", settings)
    config = load_config(BUNDLED_CONFIG)
    config["paths"]["data_dir"] = str(tmp_path / "data")
    return create_app(config, settings), config


def _client(app):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    return TestClient(app, base_url="http://127.0.0.1")


def test_saved_style_applies_now_and_after_a_restart(tmp_path):
    app, config = _app(tmp_path)
    client = _client(app)
    assert client.get("/settings/caption-style").json()["font_size"] > 0

    style = {"font": "Bebas Neue", "font_size": 58, "position": "bottom", "highlight": True,
             "highlight_color": "#39FF14", "karaoke": True, "pop": False}
    got = client.put("/settings/caption-style", json=style).json()
    assert got["font_size"] == 58 and got["pop"] is False and got["words_per_caption"] == 3
    # The worker's config: the next job deep-copies this.
    assert config["clips"]["caption_style"]["font_size"] == 58

    _app2, config2 = _app(tmp_path)
    assert config2["clips"]["caption_style"] == config["clips"]["caption_style"]


@pytest.mark.parametrize("bad", [{"font": "Wingdings"}, {"color": "red"}, {"position": "left"},
                                 {"font_size": "big"}, {"karaoke": 1}])
def test_a_bad_style_is_refused_and_nothing_changes(tmp_path, bad):
    app, config = _app(tmp_path)
    client = _client(app)
    before = client.get("/settings/caption-style").json()
    assert client.put("/settings/caption-style", json=bad).status_code == 400
    assert client.get("/settings/caption-style").json() == before


def test_the_preview_is_the_engines_own_burn(tmp_path):
    from core.binaries import ffmpeg

    if not shutil.which(ffmpeg()) and not Path(ffmpeg()).exists():
        pytest.skip("FFmpeg not installed")
    app, _config = _app(tmp_path)
    res = _client(app).get("/settings/caption-style/preview",
                           params={"style": '{"font_size": 62, "highlight": true}'})
    assert res.status_code == 200 and res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"
