"""Read-only diagnostics for agents running on the same machine."""

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response

from plugins import session
from server import feedback

_TAIL_BYTES = 64 * 1024
_PRIVATE_FIELD = re.compile(
    r"(?i)\b(authorization|(?:set-)?cookie|x-clips-kitty-session|x-api-key|"
    r"(?:[\w-]+[_-])?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|token|secret|password))['\"]?\s*[:=]"
)
_URL = re.compile(r"(?i)\b(?:https?|rtmps?|wss?)://[^\s<>\"']+")
_ERRORS = """
    SELECT 'processing' AS source, id AS job_id, NULL AS clip_id,
           type AS operation, updated_at, substr(error, 1, 4096) AS error
      FROM jobs WHERE status = 'failed'
    UNION ALL
    SELECT 'publication', id, clip_id, 'publish', updated_at, substr(error, 1, 4096)
      FROM publish_jobs WHERE status = 'failed'
    UNION ALL
    SELECT 'delivery', NULL, clip_id, platform, updated_at, substr(error, 1, 4096)
      FROM clip_publishes WHERE state = 'failed'
    ORDER BY updated_at DESC, source, job_id DESC, clip_id DESC, operation
    LIMIT ?
"""


def _redact(line: str, session_secret: str) -> str:
    if _PRIVATE_FIELD.search(line):
        return "[linha ocultada: credencial]"
    text = line.replace(session_secret, "[redacted]")
    return feedback.redact(_URL.sub("[url]", text))[:2000]


def _file_tail(path: Path, lines: int) -> tuple[str, list[str]]:
    try:
        with path.open("rb") as log:
            start = max(0, log.seek(0, 2) - _TAIL_BYTES)
            log.seek(start)
            chunk = log.read(_TAIL_BYTES)
    except FileNotFoundError:
        return "missing", []
    except OSError:
        return "unreadable", []
    tail = chunk.decode("utf-8", errors="replace").splitlines()
    return "available", tail[1 if start else 0:][-lines:]


def install(app: FastAPI, *, data_dir: Path, recorder_log: Path | None, session_secret: str) -> None:
    def require_session(given: str | None = Header(default=None, alias=session.HEADER)) -> None:
        if not session.matches(session_secret, given):
            raise HTTPException(403, "Sessão local do Clips Kitty necessária.")

    @app.get("/diagnostics/errors", dependencies=[Depends(require_session)])
    def errors(response: Response, limit: int = Query(default=20, ge=1, le=50)):
        """Falhas persistidas da fila de cortes e de publicação, da mais recente à mais antiga."""
        response.headers["Cache-Control"] = "no-store"
        try:
            with closing(sqlite3.connect(f"{(data_dir / 'state.db').as_uri()}?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(_ERRORS, (limit,)).fetchall()
        except sqlite3.OperationalError as exc:
            raise HTTPException(503, "O histórico da fila está indisponível. Consulte o log do motor.") from exc
        return {"errors": [
            {**dict(row), "error": "\n".join(_redact(line, session_secret) for line in row["error"].splitlines())}
            for row in rows
        ]}

    @app.get("/diagnostics/logs/{source}", dependencies=[Depends(require_session)])
    def logs(
        response: Response,
        source: Literal["engine", "recorder", "job"],
        lines: int = Query(default=40, ge=1, le=100),
        job_id: int | None = Query(default=None, ge=1),
    ):
        """Trecho limitado dos logs do motor, do gravador ou de uma tarefa da fila de cortes."""
        response.headers["Cache-Control"] = "no-store"
        if (source == "job") != (job_id is not None):
            raise HTTPException(422, "Informe job_id somente ao consultar o log de uma tarefa.")
        if source == "engine":
            status, tail = "available", feedback.recent_log(lines).splitlines()
        elif source == "recorder" and recorder_log is None:
            status, tail = "not_configured", []
        else:
            path = recorder_log if source == "recorder" else data_dir / "logs" / f"job_{job_id}.log"
            status, tail = _file_tail(path, lines)
        return {"source": source, "job_id": job_id, "status": status,
                "lines": [_redact(line, session_secret) for line in tail]}
