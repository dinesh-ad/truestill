"""Keep image-library diagnostics out of the product's output, and count what was kept out.

**The defect this exists for.** One `organize` over the format corpus put **866 lines** on the
user's stderr: 133 raw `UserWarning` lines naming a file in `site-packages/PIL`, and **~598 lines
written by libtiff and libjpeg straight to file descriptor 2** (`Fax3Decode2D: Bad code word at
line 1003 of strip 0`). §9 rules that no backend vocabulary reaches a user; *"Palette images with
Transparency expressed in bytes should be converted to RGBA images"* is advice to a programmer
using Pillow, addressed to somebody who is not there. Interleaved with progress, it makes a
working run look broken. `(aev)`

⚠ **THE COUNT IS THE POINT, NOT THE SUPPRESSION.** Discarding silently would make the run *look*
clean while hiding that anything happened - §4's fifty-fourth member, an instrument silent in the
case it exists for. Every line removed is counted and the total is reported, so "quiet" and
"nothing happened" stay distinguishable.

## Why `warnings.catch_warnings` is not used, and is deleted where it was

`scan.py` hashes on a `ThreadPoolExecutor` **by default**. `catch_warnings.__enter__` assigns
`warnings.filters` and `warnings.showwarning` - process-global module attributes - and the
CPython docs are explicit: *"if two or more threads use the `catch_warnings` class at the same
time, **the behavior is undefined**."* The suppression that used to live in
`hashing.perceptual_hash` was therefore already unsound on the default path, and widening it
would have widened the race.

The fix exists upstream and cannot be reached from here: CPython **gh-128384** filed it, the
`ContextVar` implementation (**gh-130010**) is *"Changed in version 3.14"*, and it is gated -
*"If unset, [`-X context_aware_warnings`] defaults to `1` on free-threaded builds and to `0`
otherwise."* ⚠ **This project moved to 3.14 on 2026-08-22 (`DECISIONS.md` D13) and the argument is
unchanged**, which is why it is stated as a flag rather than as a version: measured on 3.14.4, the
flag is **`0`**. Upgrading did not turn it on and no upgrade will, short of a free-threaded build. **JAX hit the same wall** (jax-ml/jax#25626) and hooks the
warning infrastructure rather than using the context manager. So does this.

**So the global state is written exactly once per process and never again**, which makes the
thread question disappear instead of managing it: there is no window to race over.

## No thread-local, and that is a design decision rather than an omission

An earlier shape gave each decode a thread-local naming its file so warnings could be attributed
per file. It is not needed, and it would be harmful: `_hash_one` **already returns the path** it
worked on, so per-file facts ride the return path in `HashJobResult`. A thread-local would be a
second encoding of a fact the return value already holds, with nothing forcing the two to agree.
What a person is told is derived from the decode **outcome** - see `organizer.uncompared_photos` -
and never from whether a library happened to say something: measured on the corpus, **only 71 of
478 undecodable photos warned at all**, and **14 files warned while decoding perfectly well**.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import threading
import warnings
from collections.abc import Iterator
from dataclasses import dataclass

#: Matched against the warning's originating module name. `warnings.warn` derives that from the
#: calling frame's ``__name__``, and Pillow calls it with the default stacklevel, so every warning
#: this module is written about arrives as ``PIL.something``. Narrow on purpose: a project
#: `DeprecationWarning` must still reach a developer.
_PIL_MODULE = r"PIL\..*"

#: The categories routed into the counter. **Two, not one, and the second was a bug caught by
#: this repo's own `filterwarnings = ["error"]` setting**: every warning measured on the corpus is
#: a `UserWarning`, but `Image.DecompressionBombWarning` subclasses **RuntimeWarning**, so a
#: `UserWarning`-only scope silently stopped covering the one warning `perceptual_hash` had
#: suppressed by name since it was written. Widening to bare `Warning` is deliberately NOT done:
#: a `DeprecationWarning` from Pillow is addressed to *this project's* developers and must keep
#: reaching them, which is exactly the audience the swallowed ones do not have.
_SWALLOWED = (UserWarning, RuntimeWarning)

#: The descriptor C libraries write diagnostics to. Named because it appears three times below
#: and because "2" in `fileno() == 2` reads as an arbitrary number rather than as *stderr*.
_STDERR_FD = 2


class _Tally:
    """The process's install flag and warning count, in an object rather than module globals.

    Not style. Two module-level `global` statements is the shape that makes "installed once" hard
    to reason about, and this module's entire argument is that the global write happens **exactly
    once**. One object with one lock states that; two rebindable module names do not.
    """

    __slots__ = ("count", "hook", "lines", "lock", "suppressed")

    def __init__(self) -> None:
        self.lock = threading.Lock()
        #: The `showwarning` we installed, or ``None``. Identity is the install check: anything
        #: else in that slot means somebody replaced us and we are not in force.
        self.hook: object = None
        #: Drained per task by `take_warnings`, so a child process can ship its tally home.
        self.count = 0
        #: The run's totals. Cumulative for the process lifetime and deliberately never reset:
        #: a CLI process runs one command, so cumulative IS the run. A long-lived server takes a
        #: `snapshot()` delta around its job instead - which is the honest granularity anyway,
        #: because fd 2 is process-wide and two concurrent jobs could not be told apart.
        self.suppressed = 0
        self.lines = 0


_state = _Tally()


@dataclass(frozen=True, slots=True)
class DecodeNoise:
    """How much library output was kept away from the user during one phase.

    Two numbers rather than one because they are removed by two different mechanisms and only
    one of them is a Python warning - a reader who sees them summed cannot tell that the C half
    exists, and the C half is the larger.
    """

    warnings: int
    decoder_lines: int

    @property
    def total(self) -> int:
        return self.warnings + self.decoder_lines

    def __bool__(self) -> bool:
        return self.total > 0


def _in_force() -> bool:
    """Is our hook still the live one, and our filter still in the list?

    ⚠ **Asked every time rather than remembered, and a red test is why.** A plain
    ``if installed: return`` is wrong because `warnings.catch_warnings` **restores both**
    `warnings.filters` and `warnings.showwarning` on exit - so any code anywhere in the process
    that used the context manager across our install silently un-installs us, permanently, while
    a boolean flag still says we are fine. pytest does exactly that around every test.
    """
    if warnings.showwarning is not _state.hook:
        return False
    # ⚠ The stored module entry is a COMPILED pattern, not the string that was passed in - the
    # first version of this compared it against the string, found no match, and re-installed on
    # every call. Harmless there and wrong here: it would have hidden the very clobbering the
    # check exists to detect, by always claiming we were absent.
    return any(getattr(entry[3], "pattern", None) == _PIL_MODULE for entry in warnings.filters)


def install() -> None:
    """Route the image libraries' warnings into a counter. Idempotent and self-healing.

    ⚠ **Called from BOTH places on purpose, and each has its own test.** `pool="thread"` is the
    DEFAULT, so the parent-side call is the one that carries the common path; a
    `ProcessPoolExecutor`'s children are separate interpreters and get it through
    ``initializer=``. Installing in only one of the two leaves the other unhooked and every test
    green - the failure would be invisible exactly where the code actually runs.

    ⚠ **NEVER passed as a ThreadPoolExecutor initializer.** A thread pool's initializer runs in
    each worker *thread of this process*, so it would write global state concurrently with other
    workers - the precise condition this module exists to avoid. The parent call already covers
    every thread, because they share the interpreter.

    **Re-asserting is not per-file mutation.** It happens at a phase boundary, under a lock,
    before any worker starts - never while decoding is in flight - so the undefined-behaviour
    window `catch_warnings` opens is still never opened here.
    """
    with _state.lock:
        if _in_force():
            return
        for category in _SWALLOWED:
            warnings.filterwarnings("always", category=category, module=_PIL_MODULE)
        previous = warnings.showwarning

        # ⚠ The six parameters are CPython's `showwarning` contract, not a choice - a hook with
        # a different arity is called with these anyway and raises. Hence the suppression, which
        # is the narrow kind §5 allows: the rule is right and this one signature is not ours.
        def _swallow(  # noqa: PLR0913, PLR0917
            message: Warning | str,
            category: type[Warning],
            filename: str,
            lineno: int,
            file: object = None,
            line: str | None = None,
        ) -> None:
            if issubclass(category, _SWALLOWED) and f"{os.sep}PIL{os.sep}" in filename:
                with _state.lock:
                    _state.count += 1
                return
            previous(message, category, filename, lineno, file, line)  # type: ignore[arg-type]

        warnings.showwarning = _swallow
        _state.hook = _swallow


def take_warnings() -> int:
    """Read and reset this process's pending warning tally.

    ⚠ **The value is a SUM CONTRIBUTION, never a per-task fact**, and callers must not treat it
    as one. Under a thread pool several decodes are in flight, so which task drains which
    warnings is arbitrary - but every warning is drained exactly once, so the total across all
    calls is exact. `scan._run_hash_jobs` only ever adds these up, which is why the ambiguity
    costs nothing; reading one as "how many warnings *this file* caused" would be wrong.

    Draining here rather than reading a parent-side total is what makes the number right under
    **both** pools: a `ProcessPoolExecutor` child counts in its own memory, and this rides home
    on the result.
    """
    with _state.lock:
        count, _state.count = _state.count, 0
        return count


def record_warnings(count: int) -> None:
    """Add a worker's drained tally to the run's total."""
    if count:
        with _state.lock:
            _state.suppressed += count


def snapshot() -> DecodeNoise:
    """What this process has kept out of the user's output so far.

    Read by the reporting layer rather than plumbed through `compute_hashes`, because the fact
    is genuinely process-level: fd 2 has no per-file or per-job identity, which is the same
    reason the C lines are counted rather than attributed.
    """
    with _state.lock:
        return DecodeNoise(warnings=_state.suppressed, decoder_lines=_state.lines)


@contextlib.contextmanager
def capture_decoder_output() -> Iterator[list[int]]:
    """Divert **file descriptor 2** for one phase, counting the lines C libraries write to it.

    ⚠ **This is the only mechanism that reaches the larger half.** libtiff and libjpeg do not
    raise Python warnings; they write to fd 2 directly, and no `warnings` filter, `sys.stderr`
    replacement or `capsys` touches them. Measured: ~598 of the 866 stderr lines in one corpus
    run.

    **Progress survives, and that is why `sys.stderr` is repointed rather than left alone.**
    `cli._progress_printer` writes through the `sys.stderr` *object* while the C libraries write
    to the *descriptor*; pointing the object at a duplicate of the real fd 2 separates the two, so
    a redirected descriptor silences the decoders without silencing the run.

    ⚠ **The lines are discarded rather than shown, and that is safe for one measured reason:
    they name no file.** `grep -c` for the source path over a whole 866-line run returns **0** -
    they name `tempfile.tif`, strip numbers and code words. There is nothing in them to route.

    Yields a one-element list holding the running count, so a caller can read it after the block.

    Children of a `ProcessPoolExecutor` inherit fd 2, so their decoder output lands in the same
    pipe and is counted without extra work.
    """
    counted = [0]
    try:
        original_fd = os.dup(_STDERR_FD)
    except OSError:
        # No real descriptor to divert - a test harness, an embedded interpreter, a closed
        # stderr. Doing nothing is correct and is not silent: the count stays 0, so the report
        # says nothing was suppressed, which is true of this process.
        yield counted
        return

    read_fd, write_fd = os.pipe()
    previous_stderr = sys.stderr
    # ⚠ REPOINT `sys.stderr` ONLY IF IT IS ACTUALLY BACKED BY FD 2, and this condition is not
    # defensive noise - it was a real regression. The point of repointing is to protect a stream
    # that would otherwise follow the descriptor into the pipe. An object that is NOT fd 2 -
    # pytest's capture, a `StringIO`, the app's job sink - is unaffected by the redirect, so
    # swapping it steals output from whoever installed it. It cost one red test: a progress
    # assertion went silent because the run's progress had been rerouted past the harness that
    # was watching for it.
    stderr_is_fd2 = False
    try:
        stderr_is_fd2 = previous_stderr is not None and previous_stderr.fileno() == _STDERR_FD
    except OSError, ValueError, AttributeError, io.UnsupportedOperation:
        stderr_is_fd2 = False
    reader_done = threading.Event()

    def _drain() -> None:
        with os.fdopen(read_fd, "rb", closefd=True) as pipe:
            for _line in pipe:
                counted[0] += 1
        reader_done.set()

    reader = threading.Thread(target=_drain, name="decode-noise", daemon=True)
    reader.start()
    try:
        os.dup2(write_fd, _STDERR_FD)
        os.close(write_fd)
        # The run's own progress keeps the real terminal. `closefd=False` because the finally
        # below restores fd 2 from this descriptor and then closes it exactly once.
        if stderr_is_fd2:
            sys.stderr = os.fdopen(original_fd, "w", closefd=False)
        yield counted
    finally:
        # ⚠ EVERY STEP IN A FINALLY. A leaked redirect loses all subsequent output from the
        # process, which is a far worse failure than the noise this removes - and on Windows it
        # is not recoverable from inside the run.
        if stderr_is_fd2:
            with contextlib.suppress(OSError, ValueError):
                sys.stderr.flush()
            sys.stderr = previous_stderr
        os.dup2(original_fd, _STDERR_FD)
        os.close(original_fd)
        reader_done.wait(timeout=5.0)
        with _state.lock:
            _state.lines += counted[0]
