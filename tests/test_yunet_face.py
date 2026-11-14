"""Face refinement with YuNet, the Haar cascades as the fallback.

_face_box finds the face inside a person box (the box centres on the torso in
close-ups). The Haar cascades it used miss profile and small faces (WIDER FACE
easy AP ~0.2 against YuNet's ~0.88). YuNet comes first now; the contract is
unchanged: a face box in frame pixels, or None.
"""

import threading

import pytest

np = pytest.importorskip("numpy", reason="numpy is not installed on CI")
pytest.importorskip("cv2", reason="OpenCV is not installed on CI")

import core.binaries as binaries  # noqa: E402
import video.tracker as tracker  # noqa: E402

FRAME = np.zeros((400, 400, 3), dtype=np.uint8)
BOX = (50, 50, 250, 350)   # ROI: x 50..250, y 50..200 (head = top half of the box)


def _row(x, y, w, h, score):
    return [x, y, w, h, *([0.0] * 10), score]


class FakeYuNet:
    def __init__(self, rows):
        self.rows = rows
        self.size = None
        self.shape = None

    def setInputSize(self, size):  # OpenCV's method name
        self.size = size

    def detect(self, img):
        self.shape = img.shape
        if not self.rows:
            return 0, None
        return 1, np.array(self.rows, dtype=np.float32)


@pytest.fixture(autouse=True)
def _fresh_thread_state():
    tracker._thread_local = threading.local()
    yield
    tracker._thread_local = threading.local()


def test_yunet_box_is_mapped_from_roi_to_frame(monkeypatch):
    fake = FakeYuNet([_row(10, 20, 40, 50, 0.95)])
    monkeypatch.setattr(tracker, "_get_yunet", lambda: fake)

    assert tracker._face_box(FRAME, BOX) == (60, 70, 100, 120)
    assert fake.size == (200, 150)          # the colour ROI, width x height
    assert fake.shape == (150, 200, 3)


def test_largest_confident_face_wins(monkeypatch):
    fake = FakeYuNet([_row(10, 20, 40, 50, 0.95), _row(100, 10, 60, 70, 0.95)])
    monkeypatch.setattr(tracker, "_get_yunet", lambda: fake)

    assert tracker._face_box(FRAME, BOX) == (150, 60, 210, 130)


def test_low_score_faces_fall_back_to_haar(monkeypatch):
    haar = []
    monkeypatch.setattr(tracker, "_get_yunet", lambda: FakeYuNet([_row(10, 20, 40, 50, 0.5)]))
    monkeypatch.setattr(tracker, "_get_cascades", lambda: haar.append(1))

    assert tracker._face_box(FRAME, BOX) is None
    assert haar == [1]                      # the Haar path was asked


def test_missing_model_falls_back_to_haar(monkeypatch):
    monkeypatch.setattr(binaries, "yunet_model", lambda: None)
    monkeypatch.setattr(binaries, "haar_cascade", lambda name: None)

    assert tracker._face_box(FRAME, BOX) is None


def test_missing_model_is_latched(monkeypatch):
    calls = []
    monkeypatch.setattr(binaries, "yunet_model", lambda: calls.append(1))
    monkeypatch.setattr(binaries, "haar_cascade", lambda name: None)

    for _ in range(5):
        tracker._face_box(FRAME, BOX)
    assert len(calls) == 1


def test_bundled_model_loads():
    path = binaries.yunet_model()
    if path is None:
        pytest.skip("YuNet not fetched (python scripts/fetch_yunet.py)")
    assert tracker._get_yunet() is not None
