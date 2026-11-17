"""Batching preserves sample order, bounded memory and failure recovery."""
import numpy as np
import pytest

from core import gpu
from video import tracker


class Model:
    def __init__(self, fail_batch=False, fail_gpu=False):
        self.calls = []
        self.fail_batch, self.fail_gpu = fail_batch, fail_gpu

    def predict(self, frames, **kwargs):
        assert tracker._infer_lock.locked()
        self.calls.append((frames, kwargs['device']))
        if kwargs['device'] == 'cuda' and (self.fail_gpu or
                                          (self.fail_batch and isinstance(frames, list))):
            raise RuntimeError('CUDA failure')
        return frames if isinstance(frames, list) else [frames]

    def to(self, device):
        self.moved = device


@pytest.fixture
def inference(monkeypatch):
    monkeypatch.setattr(gpu, 'torch_device', lambda: 'cuda')
    monkeypatch.setattr(tracker, '_person_detections', lambda results: results[0])


@pytest.mark.parametrize('fail_batch,fail_gpu', [(False, False), (True, False), (True, True)])
def test_batch_order_and_gpu_recovery(inference, fail_batch, fail_gpu):
    model = Model(fail_batch, fail_gpu)
    assert tracker._detect_batch(model, [1, 2, 3], .4) == [1, 2, 3]
    if fail_gpu:
        assert model.moved == 'cpu'
        model.calls.clear()
        assert tracker._detect_batch(model, [4, 5], .4) == [4, 5]
        assert [device for _, device in model.calls] == ['cpu', 'cpu']


def test_cpu_never_submits_a_batch(inference, monkeypatch):
    monkeypatch.setattr(gpu, 'torch_device', lambda: 'cpu')
    model = Model()
    assert tracker._detect_batch(model, [1, 2], .4) == [1, 2]
    assert model.calls == [(1, 'cpu'), (2, 'cpu')]


@pytest.mark.parametrize('count,fail_at', [(37, None), (37, 32), (0, None), (1, None)])
def test_sample_grid_and_partial_batch(inference, monkeypatch, count, fail_at):
    class Capture:
        idx = -1
        def grab(self):
            self.idx += 1
            return self.idx < count
        def retrieve(self):
            return self.idx != fail_at, np.full((2, 2, 3), self.idx, np.uint8)
    batches = []
    def batch(model, frames, confidence):
        ids = [int(frame[0, 0, 0]) for frame in frames]
        batches.append(ids)
        return ids
    monkeypatch.setattr(tracker, '_detect_batch', batch)
    samples = list(tracker._detected_samples(Capture(), 4, Model(), .4))
    expected = list(range(0, fail_at if fail_at is not None else count, 4))
    assert [i for i, _, _ in samples] == expected
    assert [d for _, _, d in samples] == expected
    assert all(len(b) <= 8 for b in batches)
    assert sum(batches, []) == expected


def test_initial_gpu_fallback_is_respected_by_single_and_batch(inference):
    model = Model()
    model._tracking_cpu = True
    assert tracker._detect(model, 1, .4) == 1
    assert tracker._detect_batch(model, [2, 3], .4) == [2, 3]
    assert model.calls == [(1, 'cpu'), (2, 'cpu'), (3, 'cpu')]
