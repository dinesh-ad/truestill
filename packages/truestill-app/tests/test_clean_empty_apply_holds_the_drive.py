"""The app's clean-empty apply deletes only while holding the drive's exclusion. `(agu)`

⚠ **THE DEFECT**: `server.py`'s apply route ran `service.clean_empty_apply` through a bare
`run_in_threadpool` - no in-process occupancy, no `(aaw)` DriveLock - while the CLI declared the
same command locked (`cli.py`'s map: ``"clean-empty": "path"``). The one route in the app that
DELETES, and the only mutating route outside every serialization: a CLI clean-empty's flock, or
any running job on the same drive, excluded everything except the one operation removing folders
under it. The guard built to catch exactly this
(`test_every_job_declares_whether_it_mutates.py`) parsed only `_start_drive_job` call sites, so
a route that never called it was invisible - the `(agn)` shape; its reach is fixed beside this.

**The fix is `jobs.claim`**: the exclusion HALF of `jobs.start` - same occupancy dict, same
busy wording, same DriveLock - without the job machinery, because apply is a sub-second
synchronous call whose screen contract is the result, not a job id. The headline here holds the
**CLI's own lock** (`lock_for`, the very flock `--apply` takes) around the POST: no mocks, the
real cross-process mechanism end to end, and the key spelling is shared by construction
(`drive_identity` / `drive_ref_for` both write ``uuid:``/``path:``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from truestill_app.jobs import DriveRef, JobManager
from truestill_app.server import create_app
from truestill_core.drive_lock import DriveBusyError, lock_for

TOKEN = "test-token"
_HEADERS = {"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path]:
    """A root with one genuinely empty folder - what an organize's --move leaves behind."""
    root = tmp_path / "lib"
    (root / "emptied-by-organize").mkdir(parents=True)
    return root, tmp_path / "c.sqlite"


def _apply(client: TestClient, root: Path) -> dict[str, object]:
    response = client.post(
        "/api/clean-empty/apply",
        json={"path": str(root), "emptied": ["emptied-by-organize"]},
    )
    assert response.status_code == 200
    payload: dict[str, object] = response.json()
    return payload


def test_apply_is_refused_while_another_process_holds_the_drive(
    library: tuple[Path, Path],
) -> None:
    """⚠ **THE HEADLINE - fails today by deleting straight through the CLI's lock.**"""
    root, db = library
    app = create_app(token=TOKEN, db=db)

    with (
        TestClient(app, headers=_HEADERS) as client,
        lock_for(root, operation="clean-empty"),  # what a CLI --apply holds, verbatim
    ):
        payload = _apply(client, root)

    assert payload.get("ok") is not True, "the delete ran inside another process's lock"
    assert (root / "emptied-by-organize").is_dir(), (
        "the refusal came back AND the folder was deleted anyway - the payload lied"
    )


def test_apply_still_runs_when_nothing_holds_the_drive(library: tuple[Path, Path]) -> None:
    """⚠ **CRY-WOLF HALF ONE.** A clean-empty nobody contests must still clean."""
    root, db = library
    app = create_app(token=TOKEN, db=db)

    with TestClient(app, headers=_HEADERS) as client:
        payload = _apply(client, root)

    assert payload.get("ok") is True, f"an uncontested apply was refused: {payload}"
    assert not (root / "emptied-by-organize").exists()


def test_a_second_process_is_still_refused_while_apply_holds_the_claim(
    library: tuple[Path, Path],
) -> None:
    """⚠ **CRY-WOLF HALF TWO, the other direction.** While the app's claim is held, the CLI's
    `lock_for` on the same path must refuse - same key spelling, same flock file."""
    root, _db = library
    manager = JobManager()

    claimed = manager.claim(
        drives=[DriveRef(key=f"path:{root.resolve()}", label=root.name)],
        operation="clean empty",
        mutating=True,
    )
    assert not isinstance(claimed, dict), f"an uncontested claim was refused: {claimed}"
    try:
        with pytest.raises(DriveBusyError), lock_for(root, operation="clean-empty"):
            pass
    finally:
        claimed.release()

    with lock_for(root, operation="clean-empty"):  # released means released
        pass


def test_a_running_job_refuses_the_claim_and_the_claim_refuses_a_job() -> None:
    """Both directions of the in-process half, at the manager that owns the dict."""
    manager = JobManager()
    drive = DriveRef(key="uuid:A", label="Drive A")

    claimed = manager.claim(drives=[drive], operation="clean empty", mutating=False)
    assert not isinstance(claimed, dict)
    refused = manager.start(
        lambda _p, _c: {"ok": True}, drives=[drive], operation="verify", mutating=False
    )
    assert isinstance(refused, dict), "a job started on a drive a claim holds"
    assert "clean empty" in str(refused.get("error", "")), "the refusal does not name the holder"
    claimed.release()

    second = manager.claim(drives=[drive], operation="clean empty", mutating=False)
    assert not isinstance(second, dict), "release did not free the drive"
    second.release()
