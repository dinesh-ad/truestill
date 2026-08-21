"""(aev) The suppression is installed once and is safe under the pool the product actually uses.

**The constraint this file exists to pin, stated by CPython rather than by us.** The 3.14 docs:
*"if two or more threads use the `catch_warnings` class at the same time, **the behavior is
undefined**."* `hashing.perceptual_hash` used `catch_warnings` and `scan.compute_hashes` defaults
to ``pool="thread"``, so the old suppression was unsound on the **default** path - and widening it
to cover the other 133 warnings would have widened the race rather than fixed anything.

The upstream fix exists and cannot be reached: CPython gh-128384 filed it, the `ContextVar`
implementation gh-130010 is *"Changed in version 3.14"*, and *"[it] defaults to `1` on
free-threaded builds and to `0` otherwise"*. This project runs 3.13. JAX hit the same wall
(jax-ml/jax#25626) and hooks the warning infrastructure instead; so does `decode_noise`.

⚠ **The property below is stronger than "no warning leaked".** It is that the module never
*mutates* the filter list while work is in flight - the thing that has no defined behaviour. A
test that only checked output would pass for a `catch_warnings` implementation on a lucky run.
"""

from __future__ import annotations

import multiprocessing
import re
import subprocess
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image
from truestill_core import decode_noise, scan
from truestill_core.hashing import perceptual_hash
from truestill_core.scan import compute_hashes

#: Mirrors `decode_noise._SWALLOWED`. Named here rather than imported so the guard cannot be
#: satisfied by the same edit that breaks it (§4's twenty-ninth member).
_SWALLOWED_CATEGORIES = (UserWarning, RuntimeWarning)

_THREADS = 8
_FILES = 200


def _warning_photo(path: Path) -> None:
    """A palette PNG with byte transparency - Pillow warns on every `convert`, deterministically."""
    image = Image.new("P", (32, 32))
    image.putpalette(b"".join(bytes((i, i, i)) for i in range(256)))
    image.save(path, "PNG", transparency=bytes(range(256)))


def test_the_filter_list_is_identical_before_and_after_concurrent_decoding(tmp_path: Path) -> None:
    """⚠ THE LOAD-BEARING ASSERTION. Global state is not touched while threads are decoding.

    `catch_warnings` cannot satisfy this by construction: entering it *is* an assignment to
    `warnings.filters`. Installing once and never again makes the question disappear rather than
    managing it - there is no window to race over.
    """
    decode_noise.install()  # the one global write, before anything is measured
    paths = []
    for index in range(_FILES):
        path = tmp_path / f"p{index:03d}.png"
        _warning_photo(path)
        paths.append(path)

    before = list(warnings.filters)

    with ThreadPoolExecutor(max_workers=_THREADS) as pool:
        results = list(pool.map(perceptual_hash, paths))

    after = list(warnings.filters)
    assert results.count(None) == 0, "fixture check: every file must have decoded"
    assert before == after, (
        "the warning filter list changed while 8 threads were decoding. That is the exact "
        "condition CPython documents as undefined behaviour, and it is what catch_warnings does."
    )


def test_every_concurrent_warning_is_counted_exactly_once(tmp_path: Path) -> None:
    """The tally is exact under threads, which is what lets the run state a number.

    ⚠ Attribution between tasks is arbitrary and deliberately unused - `take_warnings` says so.
    The **sum** is the claim, and it is checkable: 200 files, one warning each.
    """
    decode_noise.install()
    paths = []
    for index in range(_FILES):
        path = tmp_path / f"q{index:03d}.png"
        _warning_photo(path)
        paths.append(path)
    decode_noise.take_warnings()  # start from a known zero

    with ThreadPoolExecutor(max_workers=_THREADS) as pool:
        list(pool.map(perceptual_hash, paths))

    assert decode_noise.take_warnings() == _FILES, (
        "warnings were lost or double-counted across threads, so the number the run reports "
        "would be wrong in the only case anyone reads it"
    )


def test_a_repeat_warning_is_still_counted(tmp_path: Path) -> None:
    """⚠ Why the filter action is ``"always"`` and not the default, proved rather than asserted.

    `warn_explicit` consults the calling module's `__warningregistry__` **before** dispatching to
    `showwarning`, so under the default action a repeat never reaches the hook. Measured on the
    corpus: **197 warnings raised, 133 printed**. A hook installed without the ``"always"`` filter
    would count 133 and report it as the truth.
    """
    decode_noise.install()
    path = tmp_path / "same.png"
    _warning_photo(path)
    decode_noise.take_warnings()

    for _ in range(5):
        perceptual_hash(path)

    assert decode_noise.take_warnings() == 5, (
        "repeats were swallowed by Pillow's own warning registry before the hook saw them, so "
        "the reported count would understate what was suppressed"
    )


def test_a_project_deprecation_warning_still_reaches_a_developer() -> None:
    """The scope is narrow on purpose: this silences a library's chatter, not the whole process.

    A `DeprecationWarning` is addressed to *this project's* developers - the audience the
    swallowed warnings do not have - so widening to bare `Warning` would trade one silent failure
    for another. Nothing outside Pillow is touched either, which this checks in one step.
    """
    decode_noise.install()

    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        warnings.warn("a project deprecation", DeprecationWarning, stacklevel=1)
        warnings.warn("someone else's user warning", UserWarning, stacklevel=1)

    messages = [str(w.message) for w in seen]
    assert "a project deprecation" in messages, "a deprecation aimed at us was swallowed"
    assert "someone else's user warning" in messages, (
        "a warning from outside Pillow was swallowed; the hook must be scoped by module"
    )


def test_the_process_pool_path_installs_in_its_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The second install point - and it is forced onto **spawn**, which is the whole test.

    A `ProcessPoolExecutor` child is a separate interpreter under `spawn`: it inherits no filters
    and no hook, so without ``initializer=`` its warnings print from a process nobody is watching
    and its tally never comes home. `--pool process` is a real user-facing flag (`cli.py`), not a
    test-only path.

    ⚠ **On Linux the default start method is `fork`, where the child inherits the parent's memory
    and the initializer changes nothing** - so a test that simply called `compute_hashes` here
    could not fail, and one did not: deleting the initializer left it green. macOS and Windows
    default to **spawn**, where it is load-bearing, and both are CI lanes. Forcing the context
    makes this machine test what those machines run. §4's fifty-second member, aimed at a
    platform rather than at an empty subject.
    """
    real = scan.ProcessPoolExecutor

    def spawning(**kwargs: object) -> object:
        return real(mp_context=multiprocessing.get_context("spawn"), **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(scan, "ProcessPoolExecutor", spawning)

    paths = []
    for index in range(6):
        path = tmp_path / f"r{index}.png"
        _warning_photo(path)
        paths.append(path)
    decode_noise.take_warnings()
    # ⚠ A DELTA, NOT THE TOTAL. `snapshot()` is cumulative for the process and never reset, so an
    # earlier test in this file leaves hundreds behind: the first version asserted
    # `>= len(paths)` against that total and passed with the initializer deleted.
    before = decode_noise.snapshot().warnings

    hashes = compute_hashes(paths, pool="process", workers=2)

    assert all(h.perceptual is not None for h in hashes.values()), "every file must have hashed"
    assert decode_noise.snapshot().warnings - before == len(paths), (
        "a spawned child warned into its own memory and the count never came home; on macOS and "
        "Windows the run would report less noise than it suppressed"
    )


def test_the_thread_pool_path_counts_without_a_worker_initializer(tmp_path: Path) -> None:
    """The DEFAULT path, and the one an initializer-only install would leave unhooked.

    `pool="thread"` is `compute_hashes`' default, so this is what almost every run does. It is
    covered by the parent-side `install()` and deliberately gets **no** worker initializer: a
    thread pool's initializer runs in each worker thread of this process, which would write
    global warning state concurrently with other workers.
    """
    paths = []
    for index in range(6):
        path = tmp_path / f"s{index}.png"
        _warning_photo(path)
        paths.append(path)
    decode_noise.take_warnings()
    before = decode_noise.snapshot().warnings

    compute_hashes(paths, pool="thread", workers=4)

    assert decode_noise.snapshot().warnings - before == len(paths), (
        "the default path did not count its warnings, so an initializer-only install would look "
        "green while the common case leaked"
    )


#: Run in a child because the subject IS file descriptor 2. In-process, pytest has already
#: replaced it, so a leaked redirect would be invisible - the defect could not be observed by the
#: harness meant to catch it.
_FD_PROBE = """
import os, sys
from truestill_core import decode_noise

mode = sys.argv[1]
if mode == "raises":
    try:
        with decode_noise.capture_decoder_output():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
else:
    with decode_noise.capture_decoder_output():
        os.write(2, b"swallowed\\n")

os.write(2, b"AFTER-THE-BLOCK\\n")
print(decode_noise.snapshot().decoder_lines)
"""


@pytest.mark.parametrize("mode", ["normal", "raises"])
def test_file_descriptor_two_is_restored_even_when_the_body_raises(mode: str) -> None:
    """⚠ The worst failure this module can have, and it is worse than the noise it removes.

    A leaked redirect means **every later line the process writes to stderr is gone** - errors,
    tracebacks, the report itself - and on Windows there is no recovering it from inside the run.
    So the restore is in a `finally`, and this proves it in both directions: a clean exit and an
    exception through the block.

    ⚠ **A SUBPROCESS, because the subject is fd 2 itself.** pytest has already replaced the
    descriptor by the time a test runs, so an in-process version could not see a leak - it would
    be a guard blind to the one thing it exists for. A surviving mutation is what said so: with
    the restore deleted, nothing in the suite went red.
    """
    run = subprocess.run(
        [sys.executable, "-c", _FD_PROBE, mode],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert run.returncode == 0, f"the probe itself failed: {run.stderr[:400]}"
    assert "AFTER-THE-BLOCK" in run.stderr, (
        "stderr never came back after the capture block, so everything the process wrote "
        f"afterwards was lost. stderr={run.stderr!r}"
    )
    assert "swallowed" not in run.stderr, "the capture did not divert the descriptor at all"
    if mode == "normal":
        assert run.stdout.strip() == "1", "the diverted line was not counted"


def test_progress_written_through_sys_stderr_survives_the_capture() -> None:
    """The other half of the split: the run's own output must not go into the pipe with the noise.

    `cli._progress_printer` writes through the `sys.stderr` **object** while C libraries write to
    the **descriptor**. Repointing the object at a duplicate of the real fd 2 is what separates
    them, and without it a redirect silences the run along with the decoders.
    """
    probe = """
import os, sys
from truestill_core import decode_noise
with decode_noise.capture_decoder_output():
    os.write(2, b"decoder chatter\\n")
    print("  hashing: 3/3", file=sys.stderr, flush=True)
"""
    run = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, check=False
    )

    assert run.returncode == 0, run.stderr[:400]
    assert "hashing: 3/3" in run.stderr, (
        "the run's own progress was captured along with the library noise, so a long organize "
        "would look frozen"
    )
    assert "decoder chatter" not in run.stderr, "the library's output was not diverted"


#: A warning raised from **inside `truestill_core.hashing`** during a real hashing pass, next to a
#: file that makes Pillow warn on the same pass. Compiled under that module's own filename and
#: namespace, so `warnings.warn` attributes it exactly as our own code is attributed - which is
#: the whole question: the filter matches on module, so a synthetic frame would not prove it.
_SCOPE_PROBE = """
import pathlib, sys, warnings
from truestill_core import decode_noise, hashing
from truestill_core.scan import compute_hashes
import truestill_core.scan as scan

real = hashing.perceptual_hash
src = (
    "def perceptual_hash(path, algorithm='dhash'):\\n"
    "    warnings.warn('TRUESTILL-OWN-SIGNAL', UserWarning, stacklevel=1)\\n"
    "    return _real(path, algorithm)\\n"
)
ns = {"__name__": "truestill_core.hashing", "warnings": warnings, "_real": real}
exec(compile(src, hashing.__file__, "exec"), ns)
hashing.perceptual_hash = ns["perceptual_hash"]
scan.perceptual_hash = ns["perceptual_hash"]

compute_hashes([pathlib.Path(sys.argv[1])])
print(decode_noise.snapshot().warnings)
"""


def test_a_warning_from_our_own_code_still_reaches_the_terminal(tmp_path: Path) -> None:
    """⚠ **WE DO NOT SILENCE OUR OWN SIGNALS**, and this is the assertion that holds it.

    The suppression is scoped to the external library twice over, independently: the filter
    matches ``module=PIL\\..*``, and the hook only swallows when the raising file sits under a
    `PIL` directory. Everything else is handed to the previous `showwarning`.

    ⚠ **The probe raises from inside `truestill_core.hashing` itself** - compiled under that
    module's real filename and namespace - because attribution is exactly what is being tested.
    A `warnings.warn` written in this test file would live in a test module and prove a weaker
    thing. And it runs in a **subprocess**: pytest wraps every test in `catch_warnings`, so
    "reaches the terminal" is not observable in-process.

    Both warnings happen on the same pass over the same file, so this discriminates rather than
    merely checking that something got through.
    """
    photo = tmp_path / "palette.png"
    _warning_photo(photo)

    run = subprocess.run(
        [sys.executable, "-c", _SCOPE_PROBE, str(photo)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert run.returncode == 0, f"the probe itself failed: {run.stderr[:500]}"
    assert "TRUESTILL-OWN-SIGNAL" in run.stderr, (
        "a warning raised by Truestill's own code was swallowed. The suppression exists to stop "
        f"showing a venv path and a line number, not to silence us.\nstderr={run.stderr!r}"
    )
    located = "our warning reached the terminal but not with our own location, so a developer "
    assert "truestill_core" in run.stderr, located + "could not find which package raised it"
    assert "hashing.py" in run.stderr, located + "could not find which file raised it"
    # ...and Pillow's, on the same pass over the same file, did NOT.
    assert "Palette images" not in run.stderr, "the library's warning leaked through"
    assert "site-packages" not in run.stderr, "a venv path reached the terminal"
    assert run.stdout.strip() == "1", (
        "the library warning was neither shown nor counted; 598 lines discarded with nothing "
        "said is an instrument silent in the case it exists for"
    )


def test_the_installed_filters_do_not_reach_our_own_modules() -> None:
    """The **filter's** scope, guarded independently of the hook's. `(aev)`

    ⚠ **A surviving mutation is why this exists.** Widening `_PIL_MODULE` to `.*` broke nothing:
    the hook's filename check still refused to swallow our warnings, so every behavioural test
    stayed green. Two defences over one property, and only one of them was pinned - §4's eighth
    member, where removing either alone still passes.

    **The filter's scope is load-bearing in its own right.** Its action is ``"always"``, which
    overrides whatever the process configured: at `.*` it would force every `UserWarning` and
    `RuntimeWarning` in the program to print on every repeat and would **silently defeat a
    `-W error` setting** - including this repo's own `filterwarnings = ["error"]`. Scoped to
    Pillow it can only affect Pillow.
    """
    decode_noise.install()

    ours = "truestill_core.hashing"
    overreaching = [
        entry[3].pattern
        for entry in warnings.filters
        if entry[0] == "always"
        and entry[2] in _SWALLOWED_CATEGORIES
        and getattr(entry[3], "pattern", None) is not None
        and re.match(entry[3].pattern, ours) is not None
    ]

    assert not overreaching, (
        f"an installed 'always' filter matches our own module {ours!r}: {overreaching}. It would "
        f"override the process's configured action for every warning we raise, including a "
        f"-W error setting."
    )
