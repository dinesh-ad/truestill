#!/usr/bin/env bash
# Run a command under a hard time bound, once more if the bound killed it.
#
# ⚠ WHY THIS EXISTS RATHER THAN apt's OWN TIMEOUT. `apt` on noble carries
# https://bugs.launchpad.net/bugs/2003851: a queue-ordering deadlock where a source that fails
# with a retry-after delay is queued behind lower-priority items, and workers waiting on
# half-closed connections never receive new instructions. Measured on run 32302928420, apt reached
# a WORKING mirror in 16 s and then hung 19m54s on a 126 kB file. `Acquire::http::Timeout` was set,
# was honoured elsewhere, and did not bound it - the bug report says so explicitly: it "merely
# times out each source rather than preventing the hang entirely". Fixed upstream in apt 3.1.3
# (June 2025); noble had not received the backport as of February 2026, and the runners are noble.
#
# 🔑 THE DEADLOCK IS PER-PROCESS, WHICH IS WHY KILLING IT IS THE FIX. A second attempt gets a fresh
# apt with an empty queue, so the ordering that deadlocked is not reconstructed. This is not a
# retry loop papering over a flaky network - it is the documented remedy for a hang that the
# process cannot escape on its own.
#
# NEVER SILENT: a swallowed timeout prints what was killed and how long it had. A retry wrapper
# that hides what it retried turns an outage into a slow day nobody investigates.
set -uo pipefail

seconds="${1:?usage: ci_bounded.sh <seconds> <command...>}"
shift

attempt() {
  timeout --signal=TERM --kill-after=10s "$seconds" "$@"
}

# ⚠ `if cmd; then ...; fi` with no else leaves $? as ZERO when cmd fails - the `if` itself
# succeeded. Capturing in the else branch is the form that keeps the command's status, and the
# first draft of this script got it wrong and reported every timeout as "exit 0, not a timeout".
if attempt "$@"; then
  exit 0
else
  status=$?
fi

# 124 is timeout(1)'s "the bound killed it". Anything else is the command's own failure and must
# NOT be retried - a package that does not exist will not exist the second time either.
if [ "$status" -ne 124 ]; then
  echo "ci_bounded: '$*' failed with exit ${status} (not a timeout). Not retrying." >&2
  exit "$status"
fi

echo "" >&2
echo "ci_bounded: TIMED OUT after ${seconds}s, killed and retrying ONCE: $*" >&2
echo "  This is apt LP#2003851 if the command is apt-based - a per-process queue deadlock." >&2
echo "  The retry gets a fresh process with an empty queue. If it also times out, the" >&2
echo "  step fails and that is a real signal, not a flake." >&2
echo "" >&2

if attempt "$@"; then
  echo "ci_bounded: the retry succeeded. The first attempt was a hang, not a failure." >&2
  exit 0
else
  status=$?
fi
echo "ci_bounded: the retry also ended with exit ${status}. Failing the step." >&2
exit "$status"
