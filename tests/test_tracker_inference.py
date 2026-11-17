"""A failed CUDA warmup must stay on CPU for the real tracking frames."""
import sys
from types import SimpleNamespace

import pytest

from core import binaries, gpu
from video import tracker


class Model:
    def __init__(self):
        self.devices = []
        self.moves = []

    def to(self, device):
        self.moves.append(device)

    def predict(self, frame, *, device, **kwargs):
        assert tracker._infer_lock.locked()
        self.devices.append(device)
        if device == 'cuda':
            raise RuntimeError('GPU kernel unavailable')
        return []


def test_failed_warmup_stays_on_cpu_across_real_frames(monkeypatch):
    model = Model()
    monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=lambda _: model))
    monkeypatch.setattr(binaries, 'yolo_weights', lambda _: 'local-weights.pt')
    monkeypatch.setattr(gpu, 'cuda_usable', lambda: (True, 'test GPU'))
    # The hardware probe alone says CUDA works. Only warmup knows it failed.
    monkeypatch.setattr(gpu, 'torch_device', lambda: 'cuda')
    monkeypatch.setattr(tracker, '_model', None)
    assert tracker._get_model('pose.pt') is model
    assert tracker._detect(model, object(), .4) == []
    assert tracker._get_model('pose.pt') is model
    assert tracker._detect(model, object(), .4) == []
    assert model.moves == ['cuda', 'cpu']
    assert model.devices == ['cuda', 'cpu', 'cpu']


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_regular_detector_keeps_explicit_device(monkeypatch, device):
    calls = []
    def predict(frame, **kwargs):
        assert tracker._infer_lock.locked()
        calls.append(kwargs)
        return []
    model = SimpleNamespace(predict=predict)
    monkeypatch.setattr(gpu, 'torch_device', lambda: device)
    assert tracker._detect(model, object(), .4) == []
    assert calls == [dict(classes=[0], conf=.4, device=device, verbose=False)]
