"""Adding a video file from this computer, through the real API.

What the file brings into its job: the chosen options (Vertical Live among
them), `force` (so "Make clips again" on a file already clipped really runs
again), and its original link when the user gives one. And the shape check
the Generate bar asks before a file is added.
"""

import json
import subprocess

import pytest

from core.state import StateDB


def _ffmpeg_or_skip() -> str:
    from core.binaries import ffmpeg

    binary = ffmpeg()
    try:
        subprocess.run([binary, "-version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("FFmpeg isn't available")
    return binary


@pytest.fixture
def api(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    pytest.importorskip("numpy")
    from fastapi.testclient import TestClient

    from main import BUNDLED_CONFIG, load_config
    from server.api import create_app

    data_dir = tmp_path / "data"
    config = load_config(BUNDLED_CONFIG)
    config["paths"]["data_dir"] = str(data_dir)
    app = create_app(config, tmp_path / "settings.yaml")
    # No `with` block: startup never runs, so no worker thread picks the job up.
    return TestClient(app, base_url="http://127.0.0.1"), data_dir


def _video(tmp_path, size: str) -> str:
    binary = _ffmpeg_or_skip()
    path = tmp_path / f"live_{size}.mp4"
    subprocess.run([binary, "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30",
                    "-f", "lavfi", "-i", "sine", "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)
    return str(path)


def _job(data_dir, job_id: int) -> dict:
    db = StateDB(data_dir / "state.db")
    try:
        return json.loads(db.get_job(job_id)["payload"])
    finally:
        db.conn.close()


def test_the_generate_bar_can_ask_a_files_shape_first(api, tmp_path):
    client, _ = api
    tall = client.get("/videos/local/shape", params={"path": _video(tmp_path, "1080x1920")}).json()
    wide = client.get("/videos/local/shape", params={"path": _video(tmp_path, "1920x1080")}).json()
    assert tall == {"width": 1080, "height": 1920, "orientation": "vertical"}
    assert wide["orientation"] == "horizontal"


def test_a_vertical_live_file_keeps_its_switch_and_original_link(api, tmp_path):
    client, data_dir = api
    res = client.post("/videos/local", json={
        "path": _video(tmp_path, "1080x1920"), "vertical_live": True,
        "source_url": "https://www.tiktok.com/@someone/live"})
    assert res.status_code == 200, res.text
    payload = _job(data_dir, res.json()["job_id"])
    assert payload["vertical_live"] is True and payload["url"].startswith("local:")
    db = StateDB(data_dir / "state.db")
    try:
        row = db.conn.execute("SELECT source_url, source_platform FROM videos WHERE video_id = ?",
                              (res.json()["video_id"],)).fetchone()
    finally:
        db.conn.close()
    assert (row["source_url"], row["source_platform"]) == ("https://www.tiktok.com/@someone/live", "tiktok")


def test_make_clips_again_on_a_file_really_runs_again(api, tmp_path):
    client, data_dir = api
    res = client.post("/videos/local", json={"path": _video(tmp_path, "1920x1080"), "force": True})
    assert _job(data_dir, res.json()["job_id"])["force"] is True


# ---- #122: an H.265 file failed at transcription with InvalidDataError ------
#
# It was never the codec. A file that isn't H.264 was converted while it was
# being added, straight to its final name, which takes minutes for a long
# recording. Stopped part-way (the app closed, Generate pressed again), it left
# a half-written copy that both the import and the job took for the real thing.

def _h265(tmp_path) -> str:
    binary = _ffmpeg_or_skip()
    path = tmp_path / "recording_h265.mp4"
    made = subprocess.run(
        [binary, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=60",
         "-f", "lavfi", "-i", "sine", "-t", "3", "-c:v", "libx265", "-pix_fmt", "yuv420p10le",
         "-c:a", "aac", "-shortest", str(path)], capture_output=True)
    if made.returncode != 0:
        pytest.skip("this FFmpeg cannot encode H.265")
    return str(path)


def _half_written(path) -> None:
    """What FFmpeg leaves when it is stopped while writing an MP4: the file
    type, then media data, and no index, because the index is written last."""
    import os

    ftyp = (24).to_bytes(4, "big") + b"ftyp" + b"isom" + (512).to_bytes(4, "big") + b"isomiso2"
    free = (8).to_bytes(4, "big") + b"free"
    path.write_bytes(ftyp + free + (0).to_bytes(4, "big") + b"mdat" + os.urandom(200_000))


def test_an_h265_file_is_copied_in_not_converted(api, tmp_path):
    from video.encoding import readable_video, source_codec

    client, data_dir = api
    res = client.post("/videos/local", json={"path": _h265(tmp_path)})
    assert res.status_code == 200, res.text
    copy = data_dir / "downloads" / f"{res.json()['video_id']}.mp4"
    # Still H.265: the minutes-long conversion belongs to the job, in view.
    assert source_codec(copy) == "hevc" and readable_video(copy)
    assert [p.name for p in copy.parent.iterdir()] == [copy.name]   # no temporary file left


def test_a_half_written_copy_is_imported_again(api, tmp_path):
    from video.encoding import readable_video

    client, data_dir = api
    path = _h265(tmp_path)
    first = client.post("/videos/local", json={"path": path}).json()
    copy = data_dir / "downloads" / f"{first['video_id']}.mp4"
    _half_written(copy)
    assert not readable_video(copy)

    again = client.post("/videos/local", json={"path": path, "force": True})

    assert again.status_code == 200, again.text
    assert readable_video(copy)


def test_a_job_never_runs_on_a_half_written_copy(api, tmp_path):
    from core.pipeline import _cached_or_download

    _, data_dir = api
    copy = data_dir / "downloads" / "local_0123456789ab.mp4"
    copy.parent.mkdir(parents=True, exist_ok=True)
    _half_written(copy)
    db = StateDB(data_dir / "state.db")
    try:
        with pytest.raises(ValueError, match="did not finish importing"):
            _cached_or_download("local:local_0123456789ab", data_dir, db)
    finally:
        db.conn.close()
    assert not copy.exists()   # so adding the file again starts clean


def test_a_slow_source_is_converted_in_the_job(api, tmp_path):
    from types import SimpleNamespace

    from core.pipeline import convert_slow_source
    from main import BUNDLED_CONFIG, load_config
    from video.encoding import source_codec

    path = _h265(tmp_path)
    convert_slow_source(SimpleNamespace(path=path, video_id="local_x"), load_config(BUNDLED_CONFIG))
    assert source_codec(path) == "h264"


def test_reposting_same_local_file_recovers_queued_job_even_when_queue_full(api, tmp_path):
    from core import queue

    client, _ = api
    path = _video(tmp_path, "640x360")
    first = client.post("/videos/local", json={"path": path}).json()
    job_id, video_id = first["job_id"], first["video_id"]

    # Fill the remaining queue capacity up to MAX_ACTIVE.
    for i in range(queue.MAX_ACTIVE - 1):
        res = client.post("/jobs", json={"url": f"https://www.youtube.com/watch?v=testFill{i:03d}"})
        assert res.status_code == 200 and res.json()["job_id"]

    # Queue is full for new videos, yet retrying the same block recovers its job_id.
    new_vid = client.post("/jobs", json={"url": "https://www.youtube.com/watch?v=overflow999"})
    assert new_vid.status_code == 409

    retry_local = client.post("/videos/local", json={"path": path})
    assert retry_local.status_code == 200
    assert retry_local.json() == {
        "job_id": None, "already_queued": True, "video_id": video_id, "queued_job_id": job_id,
    }
    retry_url = client.post("/jobs", json={"url": "https://www.youtube.com/watch?v=testFill000"})
    assert retry_url.status_code == 200
    assert retry_url.json()["already_queued"] is True and isinstance(retry_url.json()["queued_job_id"], int)


def test_local_video_with_chat_saves_loads_uses_live_lag_exposes_momento_chave_and_cleans_up(
    api, tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from core import housekeeping, pipeline

    client, data_dir = api
    src = _video(tmp_path, "1280x720")
    chat_payload = [
        {"t": 18.0, "user": "alice", "text": "kkkk clipa isso", "emotes": 2},
        {"t": 12.0, "user": "bob", "text": "KEKW", "emotes": 1},
    ]
    res = client.post("/videos/local", json={
        "path": src,
        "gaming_scoring": True,
        "chat": chat_payload,
    })
    assert res.status_code == 200, res.text
    vid = res.json()["video_id"]
    chat_file = data_dir / "chats" / f"{vid}.json"
    assert chat_file.is_file()
    saved = json.loads(chat_file.read_text(encoding="utf-8"))
    assert [m["t"] for m in saved] == [12.0, 18.0]  # sorted by t
    assert saved[1]["emotes"] == 2

    # Pipeline helper reads local chat directly (sorted 4-tuples) and picks live lag (~3s vs VOD 6s).
    loaded = pipeline._local_chat(data_dir, vid)
    assert loaded == [(12.0, "bob", "KEKW", 1), (18.0, "alice", "kkkk clipa isso", 2)]

    seen_lags = []
    monkeypatch.setattr("analysis.chat_moments.chat_signal", lambda msgs, dur, classes, lag, ignore: (
        seen_lags.append(lag) or SimpleNamespace(curve=None, events=[])
    ))
    k = pipeline.gaming if False else __import__("analysis.gaming", fromlist=["knowledge"]).knowledge()
    hype_msgs = [(10.0 + i * 0.2, f"u{i}", "kkkk", 1) for i in range(15)]
    db = StateDB(data_dir / "state.db")
    try:
        cfg = {"clips": {"gaming_scoring": True}, "scoring": {}}
        pipeline._gaming_scoring_inputs(cfg, SimpleNamespace(video_id=vid, title="GTA RP", duration=60.0),
                                        db, [], {"messages": hype_msgs})
        pipeline._gaming_scoring_inputs(cfg, SimpleNamespace(video_id="tw_999", title="GTA RP", duration=60.0),
                                        db, [], {"messages": hype_msgs})
        assert seen_lags == [float(k["chat_live_lag_seconds"]), float(k["chat_lag_seconds"])]
        assert seen_lags[0] < seen_lags[1]

        # Clip response lifts momento_chave to top-level.
        mk = {"score": 0.82, "motivos": ["chat 5.1x", "kkkk"]}
        db.add_clip(vid, 1.0, 15.0, 82.0, "Clip", scores=json.dumps({"game": 70.0, "momento_chave": mk}))
    finally:
        db.conn.close()

    clips_res = client.get(f"/videos/{vid}/clips")
    assert clips_res.status_code == 200
    assert clips_res.json()[0]["momento_chave"] == mk

    # DELETE /videos/{vid} deletes its chat file too.
    del_res = client.delete(f"/videos/{vid}")
    assert del_res.status_code == 200
    assert not chat_file.exists()

    # Orphan chat files are reported by housekeeping.
    orphan = data_dir / "chats" / "local_orphan999.json"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("[]", encoding="utf-8")
    db = StateDB(data_dir / "state.db")
    try:
        survey = housekeeping.survey(db, data_dir)
        assert survey["reclaimable"]["orphan_chats"]["files"] == 1
        assert survey["_groups"]["orphan_chats"] == [orphan]
    finally:
        db.conn.close()


def test_local_video_without_chat_works_unchanged(api, tmp_path):
    from core import pipeline

    client, data_dir = api
    res = client.post("/videos/local", json={"path": _video(tmp_path, "640x360")})
    assert res.status_code == 200, res.text
    vid = res.json()["video_id"]
    assert pipeline._local_chat(data_dir, vid) == []
    assert not (data_dir / "chats" / f"{vid}.json").exists()


def test_r05_local_rejects_full_or_duplicate_before_probing_or_importing(api, tmp_path, monkeypatch):
    from core import queue

    client, _ = api
    existing_src = _video(tmp_path, "640x360")
    first = client.post("/videos/local", json={"path": existing_src})
    assert first.status_code == 200

    for i in range(queue.MAX_ACTIVE - 1):
        r = client.post("/jobs", json={"url": f"https://www.youtube.com/watch?v=capFill{i:03d}"})
        assert r.status_code == 200

    # Create a brand new valid-extension file (doesn't even need valid video bytes because
    # capacity check happens BEFORE ffprobe/import).
    fake_block = tmp_path / "overflow_block.mp4"
    fake_block.write_bytes(b"not probed when rejected early")

    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))

    # Duplicate retry returns 200 already_queued with zero ffprobe/import calls.
    dup = client.post("/videos/local", json={"path": existing_src})
    assert dup.status_code == 200 and dup.json()["already_queued"] is True
    assert calls == []

    # Queue-full rejects with 409 with zero ffprobe/import calls.
    full = client.post("/videos/local", json={"path": str(fake_block)})
    assert full.status_code == 409
    assert calls == []


def test_r05_concurrent_local_uploads_respect_max_active(api, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from core import queue

    client, data_dir = api
    src_base = _video(tmp_path, "640x360")
    raw = open(src_base, "rb").read()
    paths = []
    for i in range(queue.MAX_ACTIVE + 3):
        p = tmp_path / f"concurrent_{i}.mp4"
        p.write_bytes(raw)
        paths.append(str(p))

    with ThreadPoolExecutor(max_workers=len(paths)) as pool:
        results = list(pool.map(lambda p: client.post("/videos/local", json={"path": p}), paths))

    ok = [r for r in results if r.status_code == 200 and r.json().get("job_id")]
    rejected = [r for r in results if r.status_code == 409]
    assert len(ok) == queue.MAX_ACTIVE
    assert len(rejected) == 3
    db = StateDB(data_dir / "state.db")
    try:
        assert queue.active_count(db) == queue.MAX_ACTIVE
    finally:
        db.conn.close()
