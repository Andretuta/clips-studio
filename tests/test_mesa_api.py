"""The /mesa routes (server/mesa_api.py): the approval desk over the folders
the cola writes (saida/pendentes, aprovados, descartados) and the control
room over the recorder's folders. No network, no Kitty pipeline: cuts are
written the way the cola writes them (an mp4 and a JSON side by side)."""

import json
import os
import subprocess
import time
from datetime import datetime

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from server import mesa_api  # noqa: E402

SECRET = "test-session-secret-0123456789"
HEADERS = {"X-Clips-Kitty-Session": SECRET}
HOJE = datetime.now().strftime("%Y-%m-%d")


class FakeDB:
    """StateDB as the routes use it: get_clip and close."""

    clips: set[int] = set()

    def get_clip(self, clip_id):
        return {"id": clip_id} if clip_id in self.clips else None

    def close(self):
        pass


def corte(pasta, nome, *, nota=50, clip_id=1, streamer="jhowrj", bloco="1825", inicio=320, fim=356,
          origem=None, **campos):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42 fake video")
    origem = origem or (f"D:\\clipador-gta6\\data\\clips\\{streamer}\\{streamer} {HOJE} {bloco} "
                        f"[local_55a38fd2ff41]\\clip_{inicio:05d}-{fim:05d}.mp4")
    dados = {"streamer": streamer, "plataforma": "kick", "fonte": f"https://kick.com/{streamer}",
             "idioma_original": "pt", "titulo": f"titulo {nome}", "descricao": "desc", "hashtags": ["#gta6"],
             "nota": nota, "clip_id": clip_id, "video_id": "local_55a38fd2ff41", "arquivo_original": origem,
             "criado_em": f"{HOJE}T18:54:09", **campos}
    (pasta / f"{nome}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


@pytest.fixture
def saida(tmp_path):
    return tmp_path / "saida"


@pytest.fixture
def gravacoes(tmp_path):
    return tmp_path / "gravacoes"


def make_client(tmp_path, mesa):
    app = fastapi.FastAPI()
    mesa_api.install(app, config={"mesa": mesa}, db=FakeDB, data_dir=tmp_path, session_secret=SECRET)
    return TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def client(tmp_path, saida, gravacoes):
    FakeDB.clips = set()
    return make_client(tmp_path, {"dir": str(saida), "gravacoes_dir": str(gravacoes)})


def pendentes(saida):
    return saida / "pendentes"


# ---- listing ------------------------------------------------------------------

def test_lists_pending_cuts_best_score_first(client, saida):
    corte(pendentes(saida), "kick_a_1", nota=58, clip_id=1)
    corte(pendentes(saida), "kick_b_2", nota=74, clip_id=2)
    corte(pendentes(saida), "kick_c_3", nota=61, clip_id=3)

    r = client.get("/mesa/cortes")

    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert [c["nome"] for c in body["cortes"]] == ["kick_b_2", "kick_c_3", "kick_a_1"]
    primeiro = body["cortes"][0]
    assert primeiro["titulo"] == "titulo kick_b_2"
    assert primeiro["nota"] == 74
    assert primeiro["live"] == {"bloco": "18:25", "inicio_s": 320, "fim_s": 356}


def test_says_whether_the_clip_is_still_in_the_editor(client, saida):
    FakeDB.clips = {7}
    corte(pendentes(saida), "kick_a_7", clip_id=7)
    corte(pendentes(saida), "kick_a_8", clip_id=8)

    cortes = {c["nome"]: c for c in client.get("/mesa/cortes").json()["cortes"]}

    assert cortes["kick_a_7"]["no_editor"] is True
    assert cortes["kick_a_8"]["no_editor"] is False


def test_skips_broken_json_and_json_without_video(client, saida):
    corte(pendentes(saida), "kick_ok_1")
    (pendentes(saida) / "kick_quebrado_2.json").write_text("{nao é json", encoding="utf-8")
    (pendentes(saida) / "kick_quebrado_2.mp4").write_bytes(b"x")
    corte(pendentes(saida), "kick_sem_video_3")
    (pendentes(saida) / "kick_sem_video_3.mp4").unlink()

    r = client.get("/mesa/cortes")

    assert r.status_code == 200
    assert [c["nome"] for c in r.json()["cortes"]] == ["kick_ok_1"]


def test_counts_pending_and_todays_decisions(client, saida):
    corte(pendentes(saida), "kick_a_1")
    corte(saida / "aprovados", "kick_b_2", decidido_em=f"{HOJE}T19:00:00")
    corte(saida / "aprovados", "kick_c_3", decidido_em="2026-01-01T10:00:00")
    corte(saida / "descartados", "kick_d_4", decidido_em=f"{HOJE}T19:01:00")

    contagens = client.get("/mesa/cortes").json()["contagens"]

    assert contagens == {"pendentes": 1, "aprovados_hoje": 1, "descartados_hoje": 1, "aprovados": 2}


def test_garimpeiro_cut_has_no_live_position(client, saida):
    corte(pendentes(saida), "twitch_x_9",
          origem="D:\\clipador-gta6\\data\\clips\\chibi\\mundo pov [tw_clip_Muddy-YTwN]\\clip_00000-00030.mp4")

    assert client.get("/mesa/cortes").json()["cortes"][0]["live"] is None


# ---- video --------------------------------------------------------------------

def test_serves_the_cut_video(client, saida):
    corte(pendentes(saida), "kick_a_1")

    r = client.get("/mesa/cortes/kick_a_1/video")

    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert r.content.startswith(b"\x00\x00\x00\x18ftyp")


@pytest.mark.parametrize("nome", ["nao_existe", "..", "kick a 1", "..%2Fsegredo"])
def test_unknown_or_unsafe_name_is_404(client, saida, nome):
    corte(pendentes(saida), "kick_a_1")
    (saida / "segredo.json").write_text("{}", encoding="utf-8")

    assert client.get(f"/mesa/cortes/{nome}/video").status_code == 404
    assert client.get(f"/mesa/cortes/{nome}/capa").status_code == 404
    assert client.post(f"/mesa/cortes/{nome}/aprovar", headers=HEADERS).status_code == 404


# ---- edits and decisions --------------------------------------------------------

def test_patch_saves_title_description_and_hashtags(client, saida):
    corte(pendentes(saida), "kick_a_1")

    r = client.patch("/mesa/cortes/kick_a_1", headers=HEADERS,
                     json={"titulo": "Novo título", "descricao": "Nova", "hashtags": ["#gta6", "#vice"]})

    assert r.status_code == 200
    assert r.json()["titulo"] == "Novo título"
    salvo = json.loads((pendentes(saida) / "kick_a_1.json").read_text(encoding="utf-8"))
    assert (salvo["titulo"], salvo["descricao"], salvo["hashtags"]) == ("Novo título", "Nova", ["#gta6", "#vice"])
    assert salvo["nota"] == 50  # the rest of the cola's JSON stays


def test_changing_routes_need_the_session(client, saida):
    corte(pendentes(saida), "kick_a_1")

    assert client.patch("/mesa/cortes/kick_a_1", json={"titulo": "x"}).status_code == 403
    assert client.post("/mesa/cortes/kick_a_1/aprovar").status_code == 403
    assert client.post("/mesa/cortes/kick_a_1/descartar",
                       headers={"X-Clips-Kitty-Session": "errado"}).status_code == 403
    assert (pendentes(saida) / "kick_a_1.mp4").exists()


def test_approve_moves_video_and_json_with_the_edits(client, saida):
    corte(pendentes(saida), "kick_a_1")

    r = client.post("/mesa/cortes/kick_a_1/aprovar", headers=HEADERS,
                    json={"titulo": "Aprovado!", "destinos": ["tiktok", "shorts"]})

    assert r.status_code == 200
    assert not (pendentes(saida) / "kick_a_1.mp4").exists()
    assert not (pendentes(saida) / "kick_a_1.json").exists()
    assert (saida / "aprovados" / "kick_a_1.mp4").exists()
    salvo = json.loads((saida / "aprovados" / "kick_a_1.json").read_text(encoding="utf-8"))
    assert salvo["titulo"] == "Aprovado!"
    assert salvo["destinos"] == ["tiktok", "shorts"]
    assert salvo["decidido_em"].startswith(HOJE)


def test_discard_moves_to_descartados(client, saida):
    corte(pendentes(saida), "kick_a_1")

    r = client.post("/mesa/cortes/kick_a_1/descartar", headers=HEADERS)

    assert r.status_code == 200
    assert (saida / "descartados" / "kick_a_1.mp4").exists()
    assert (saida / "descartados" / "kick_a_1.json").exists()
    assert list(pendentes(saida).iterdir()) == []


def test_decision_never_overwrites_an_existing_file(client, saida):
    corte(saida / "aprovados", "kick_a_1", titulo="o antigo")
    corte(pendentes(saida), "kick_a_1", titulo="o novo")

    client.post("/mesa/cortes/kick_a_1/aprovar", headers=HEADERS)

    antigo = json.loads((saida / "aprovados" / "kick_a_1.json").read_text(encoding="utf-8"))
    novo = json.loads((saida / "aprovados" / "kick_a_1-2.json").read_text(encoding="utf-8"))
    assert (antigo["titulo"], novo["titulo"]) == ("o antigo", "o novo")
    assert (saida / "aprovados" / "kick_a_1-2.mp4").exists()


# ---- switched off -----------------------------------------------------------------

def test_without_a_folder_the_desk_is_off(tmp_path):
    c = make_client(tmp_path, {"dir": ""})

    assert c.get("/mesa/cortes").json() == {"enabled": False}
    assert c.get("/mesa/controle").json() == {"enabled": False}
    assert c.get("/mesa/cortes/x/video").status_code == 404


# ---- control room --------------------------------------------------------------------

def test_recording_channel_is_one_with_a_fresh_segment(client, gravacoes):
    vivo, parado = gravacoes / "kick_jhowrj", gravacoes / "twitch_falamicatv"
    vivo.mkdir(parents=True)
    parado.mkdir(parents=True)
    (vivo / "seg_001.ts").write_bytes(b"x")
    velho = parado / "seg_001.ts"
    velho.write_bytes(b"x")
    dez_min = time.time() - 600
    os.utime(velho, (dez_min, dez_min))

    canais = {c["nome"]: c for c in client.get("/mesa/controle").json()["canais"]}

    assert canais["kick_jhowrj"]["gravando"] is True
    assert canais["kick_jhowrj"]["plataforma"] == "kick"
    assert canais["kick_jhowrj"]["canal"] == "jhowrj"
    assert canais["twitch_falamicatv"]["gravando"] is False


def test_todays_lives_group_cuts_by_streamer_and_block(client, saida):
    corte(pendentes(saida), "kick_a_1", bloco="1825", inicio=320, fim=356, nota=70)
    corte(pendentes(saida), "kick_a_2", bloco="1841", inicio=10, fim=40, nota=55)
    corte(saida / "aprovados", "kick_a_3", bloco="1825", inicio=500, fim=530)
    corte(pendentes(saida), "twitch_x_9",
          origem="D:\\clipador-gta6\\data\\clips\\chibi\\mundo pov [tw_clip_Muddy-YTwN]\\clip_00000-00030.mp4")
    corte(pendentes(saida), "kick_velho_5", streamer="pepetino1",
          origem="D:\\clipador-gta6\\data\\clips\\p\\pepetino1 2026-01-01 1000 [local_ab12]\\clip_00001-00031.mp4")

    lives = client.get("/mesa/controle").json()["lives"]

    assert [lv["streamer"] for lv in lives] == ["jhowrj"]
    blocos = lives[0]["blocos"]
    assert [b["inicio"] for b in blocos] == ["18:25", "18:41"]
    primeiro = {c["nome"]: c for c in blocos[0]["cortes"]}
    assert primeiro["kick_a_1"] == {"nome": "kick_a_1", "inicio_s": 320, "fim_s": 356, "nota": 70,
                                    "estado": "pendente"}
    assert primeiro["kick_a_3"]["estado"] == "aprovado"


def test_control_room_lists_the_best_pending_cuts(client, saida):
    for i, nota in enumerate([40, 90, 60, 75, 82, 55, 70]):
        corte(pendentes(saida), f"kick_a_{i}", nota=nota)

    body = client.get("/mesa/controle").json()

    assert [c["nota"] for c in body["melhores"]] == [90, 82, 75, 70, 60]
    assert body["contagens"]["pendentes"] == 7


@pytest.mark.skipif(os.name != "nt", reason="only Windows refuses to move a file that is open")
def test_video_still_open_is_409_and_nothing_moves(client, saida):
    corte(pendentes(saida), "kick_a_1")

    with open(pendentes(saida) / "kick_a_1.mp4", "rb"):
        r = client.post("/mesa/cortes/kick_a_1/aprovar", headers=HEADERS)

    assert r.status_code == 409
    assert (pendentes(saida) / "kick_a_1.mp4").exists()
    assert (pendentes(saida) / "kick_a_1.json").exists()
    assert not (saida / "aprovados" / "kick_a_1.json").exists()


def test_channel_without_segments_is_as_old_as_its_folder(client, gravacoes):
    """The recorder deletes segments once they are cut into blocks: a folder
    left empty says when it last changed, so a stopped live still shows."""
    vazio = gravacoes / "twitch_falamicatv"
    vazio.mkdir(parents=True)
    cinco_min = time.time() - 300
    os.utime(vazio, (cinco_min, cinco_min))

    canal = client.get("/mesa/controle").json()["canais"][0]

    assert canal["gravando"] is False
    assert 290 <= canal["ultimo_s"] <= 330



# ---- covers (the list's thumbnails) ------------------------------------------------

def _ffmpeg_or_skip() -> str:
    from core.binaries import ffmpeg

    binary = ffmpeg()
    if not os.path.isfile(binary):
        pytest.skip("FFmpeg is not installed here")
    return binary


def test_cover_is_a_small_jpeg_made_once(client, saida, tmp_path):
    binary = _ffmpeg_or_skip()
    corte(pendentes(saida), "kick_a_1", inicio=0, fim=2)
    subprocess.run([binary, "-y", "-v", "error", "-f", "lavfi", "-i", "color=red:s=1080x1920:d=2",
                    "-pix_fmt", "yuv420p", str(pendentes(saida) / "kick_a_1.mp4")], check=True)

    r = client.get("/mesa/cortes/kick_a_1/capa")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == bytes([0xFF, 0xD8])  # JPEG
    assert "max-age" in r.headers["cache-control"]
    feitas = list((tmp_path / "previews" / "mesa").glob("*.jpg"))
    assert len(feitas) == 1
    assert feitas[0].stat().st_size < 30_000  # a thumbnail, not a 1080x1920 frame
    antes = feitas[0].stat().st_mtime_ns
    assert client.get("/mesa/cortes/kick_a_1/capa").content == r.content
    assert feitas[0].stat().st_mtime_ns == antes  # served from the cache, not made again


def test_cover_of_an_unreadable_video_is_404(client, saida):
    _ffmpeg_or_skip()
    corte(pendentes(saida), "kick_a_1")  # its mp4 is a few fake bytes

    assert client.get("/mesa/cortes/kick_a_1/capa").status_code == 404
