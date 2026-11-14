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


def test_yunet_finding_no_face_is_the_answer(monkeypatch):
    # The spec: YuNet replaces Haar, which only runs when YuNet cannot look.
    # On gameplay with no face, Haar invents faces (8/12 frames vs YuNet 3/12).
    haar = []
    monkeypatch.setattr(tracker, "_get_yunet", lambda: FakeYuNet([_row(10, 20, 40, 50, 0.5)]))
    monkeypatch.setattr(tracker, "_get_cascades", lambda: haar.append(1))

    assert tracker._face_box(FRAME, BOX) is None
    assert haar == []                       # Haar was not asked


def test_roi_too_small_for_yunet_asks_haar(monkeypatch):
    haar, fake = [], FakeYuNet([_row(1, 1, 10, 10, 0.95)])
    monkeypatch.setattr(tracker, "_get_yunet", lambda: fake)
    monkeypatch.setattr(tracker, "_get_cascades", lambda: haar.append(1))

    assert tracker._face_box(FRAME, (50, 50, 90, 350)) is None   # ROI 40 px wide
    assert fake.size is None and haar == [1]


def test_yunet_error_asks_haar(monkeypatch):
    class Broken(FakeYuNet):
        def detect(self, img):
            raise RuntimeError("cv2 error")
    haar = []
    monkeypatch.setattr(tracker, "_get_yunet", lambda: Broken([]))
    monkeypatch.setattr(tracker, "_get_cascades", lambda: haar.append(1))

    assert tracker._face_box(FRAME, BOX) is None
    assert haar == [1]


def test_non_finite_rows_are_dropped(monkeypatch):
    inf = float("inf")
    fake = FakeYuNet([_row(inf, inf, inf, inf, 0.99), _row(10, 20, 40, 50, 0.95)])
    monkeypatch.setattr(tracker, "_get_yunet", lambda: fake)

    assert tracker._face_box(FRAME, BOX) == (60, 70, 100, 120)


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


def test_real_model_never_raises_on_small_rois():
    # The real network returns rows with a passing score and inf coordinates
    # on ROIs of 32 px or less; int(inf) raised and took the render down.
    if binaries.yunet_model() is None:
        pytest.skip("YuNet not fetched (python scripts/fetch_yunet.py)")
    gray = np.full((600, 600, 3), 128, dtype=np.uint8)
    for w in (16, 17, 20, 24, 32, 40, 47, 48, 64):
        for box_h in (32, 80, 160, 400):
            tracker._face_box(gray, (50, 50, 50 + w, 50 + box_h))
