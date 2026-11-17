import json
import shutil
import subprocess
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import progress, queue
from core.binaries import ffmpeg, ffprobe
from core.state import StateDB
from server.compilation_api import install
from server.jobs import Worker


def test_render_order_and_format_from_mesa_and_library(tmp_path):
    if not shutil.which(ffmpeg()) or not shutil.which(ffprobe()):
        pytest.skip("FFmpeg and FFprobe are needed")
    desk = tmp_path / "saida" / "aprovados"
    desk.mkdir(parents=True)
    library = tmp_path / "clips"
    library.mkdir()
    vertical = desk / "vermelho.mp4"
    horizontal = library / "azul.mp4"
    (desk / "vermelho.json").write_text('{"titulo": "Vermelho"}', encoding="utf-8")
    subprocess.run([ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=red:s=144x256:r=24:d=0.8",
                    "-c:v", "libx264", str(vertical)], check=True)
    subprocess.run([ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=blue:s=320x180:r=25:d=0.9",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.9", "-c:v", "libx264",
                    "-c:a", "aac", "-shortest", str(horizontal)], check=True)

    def database():
        return StateDB(tmp_path / "state.db")

    state = database()
    state.upsert_video("library")
    state.set_video_status("library", "done")
    clip_id = state.add_clip("library", 0, 0.9, 80, "Azul", path=str(horizontal))
    queue.set_paused(state, False)
    config = {"paths": {"data_dir": str(tmp_path)}, "mesa": {"dir": str(desk.parent)}}
    worker = Worker(config)
    app = FastAPI()
    install(app, config=config, db=database, data_dir=tmp_path, worker=worker)
    client = TestClient(app)
    sources = {cut["id"]: cut for cut in client.get("/compilations/sources").json()}
    assert sources["mesa:vermelho"]["state"] == "aprovado"
    assert client.get("/compilations/sources/mesa:vermelho/media", headers={"Range": "bytes=0-63"}).status_code == 206
    ready = client.post("/publication/sources/mesa:vermelho/prepare")
    assert ready.status_code == 200
    prepared = state.get_clip(ready.json()["clip_id"])
    assert prepared["title"] == "Vermelho" and vertical.is_file()
    assert client.post("/publication/sources/mesa:vermelho/prepare").json() == ready.json()
    assert client.post("/compilations", json={"title": "Teste", "sources": ["mesa:..", f"clip:{clip_id}"]}).status_code == 404
    response = client.post("/compilations", json={"title": "Teste", "sources": ["mesa:vermelho", f"clip:{clip_id}"]})
    assert response.status_code == 202
    job = response.json()
    worker.start()
    try:
        deadline = time.monotonic() + 40
        row = state.get_job(job["job_id"])
        while row["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.1)
            row = state.get_job(job["job_id"])
        assert row["status"] == "done", row["error"]
        [output] = state.clips_for_video(job["video_id"])
        file = output["path"]
        assert json.loads(output["render_opts"])["profile"] == "compilation"
        info = json.loads(subprocess.check_output(
            [ffprobe(), "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
             "-of", "json", file]
        ))
        video, audio = info["streams"]
        assert (video["width"], video["height"], video["r_frame_rate"]) == (1920, 1080, "30/1")
        assert audio["codec_type"] == "audio"
        assert float(info["format"]["duration"]) == pytest.approx(1.7, abs=0.16)

        def pixel(seconds, x):
            return tuple(subprocess.check_output(
                [ffmpeg(), "-v", "error", "-ss", str(seconds), "-i", file, "-frames:v", "1",
                 "-vf", f"crop=2:2:{x}:540,scale=1:1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
            ))

        red = pixel(0.2, 960)
        blue = pixel(1.1, 960)
        assert red[0] > 200 and red[2] < 55
        assert blue[2] > 200 and blue[0] < 55
        assert max(pixel(0.2, 20)) < 20  # portrait is fitted, with the whole picture visible
    finally:
        worker.stop()
        worker.join(10)
        progress.set_handler(None)
        state.close()


def test_r08_compilation_and_render_jobs_count_toward_capacity(tmp_path):
    """R08: queue.active_count counts process, compilation, and render jobs."""
    from fastapi import HTTPException

    state = StateDB(tmp_path / "state.db")
    try:
        for i in range(queue.MAX_ACTIVE - 2):
            state.add_job("process", json.dumps({"url": f"https://youtu.be/v{i}"}), video_id=f"v{i}")
        state.add_job("compilation", json.dumps({"title": "Comp"}), video_id="comp_1")
        state.add_job("render", json.dumps({"clip_id": 1}), video_id="")
        assert queue.active_count(state) == queue.MAX_ACTIVE
        assert queue.capacity(state) == 0

        # Compilation API enqueue refuses when MAX_ACTIVE is reached.
        app = FastAPI()
        config = {"paths": {"data_dir": str(tmp_path)}, "mesa": {"dir": str(tmp_path / "mesa")}}
        install(app, config=config, db=lambda: StateDB(tmp_path / "state.db"), data_dir=tmp_path, worker=Worker(config))
        client = TestClient(app)
        res = client.post("/compilations", json={"title": "Overflow", "sources": ["clip:1", "clip:2"]})
        assert res.status_code == 409

        # Once a render job finishes, one slot opens up.
        render_id = state.conn.execute("SELECT id FROM jobs WHERE type='render'").fetchone()["id"]
        state.finish_job(render_id, status="done")
        assert queue.active_count(state) == queue.MAX_ACTIVE - 1
        assert queue.capacity(state) == 1
    finally:
        state.close()

