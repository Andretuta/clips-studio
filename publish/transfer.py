"""Prazo de parede: processo isolado, encerrável mesmo com socket em gotejamento."""

import multiprocessing
import time

from publish.receipts import UncertainDelivery

TOTAL_SECONDS = 300


def _child(pipe, key, data, file):
    try:
        from publish.composio import _upload
        identifier = _upload(key, data, file, lambda: False,
                             submitting=lambda: pipe.send(("submitting", "")))
        pipe.send(("done", identifier))
    except Exception:
        # Provider exceptions may contain credentials. Nothing raw crosses IPC.
        pipe.send(("error", ""))
    finally:
        pipe.close()


def bounded_upload(key, data, file, cancelled, submitting, *, seconds=TOTAL_SECONDS):
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(sender, key, data, file), daemon=True)
    deadline = time.monotonic() + seconds
    attempted = False
    process.start()
    sender.close()
    try:
        while time.monotonic() < deadline:
            if cancelled():
                from publish.errors import PublishCancelled
                if attempted:
                    raise UncertainDelivery("Envio interrompido após submissão; confira o canal antes de repetir.")
                raise PublishCancelled("Envio cancelado antes da submissão.")
            if receiver.poll(min(.1, max(0, deadline - time.monotonic()))):
                try:
                    state, identifier = receiver.recv()
                except EOFError:
                    break
                if state == "submitting":
                    attempted = True
                    submitting()
                elif state == "done":
                    return identifier
                else:
                    break
            elif not process.is_alive():
                break
        if attempted:
            raise UncertainDelivery("Prazo/transferência encerrado sem confirmação. Confira o canal e reconcilie antes de repetir.")
        from publish.errors import PublishError
        raise PublishError("A transferência não concluiu no prazo total de cinco minutos; nada foi submetido ao canal.")
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        receiver.close()
