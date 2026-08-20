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
# ⚠ THE PAUSE IS NOT BACKOFF, AND CALLING IT BACKOFF WOULD INVITE SOMEONE TO "IMPROVE" IT INTO
# EXPONENTIAL BACKOFF WITH JITTER. Three parts of that pattern's rationale do not apply here:
#
#   * **We never see the 503.** The standard advice is "retry only transient errors - 429, 503,
#     504". apt swallows the status and DEADLOCKS, so our only observable is exit 124, a hang.
#     A rule keyed on status codes cannot be written against a signal we do not receive.
#   * **One gap cannot grow.** "Exponential" describes growth ACROSS successive retries. With two
#     attempts there is exactly one interval, and nothing to be exponential about. Meaningful
#     backoff would require three or more attempts - rejected on arithmetic, see below.
#   * **Jitter answers a thundering herd we do not have.** It desynchronises many clients. This
#     workflow has four jobs and they are already staggered by seconds.
#
# What DOES survive, and justifies the delay on its own grounds: the trigger is a server-side
# temporary failure that may still be in force, and an immediate retry re-enters it with nothing
# changed but the queue. Thirty seconds is a pause to let a transient condition pass, not a
# politeness ramp.
#
# ⚠ WHY NOT THREE ATTEMPTS - the arithmetic is the whole argument. The `check` job's bound is 20
# minutes and must not rise (`(aec)`: a bound that fires during an outage is correctly sized).
# Three attempts at 180 s plus backoff is ~585 s per apt call, two calls per job, ~22 min - it
# BREACHES the bound. Three at 120 s fits, but 120 s is only 1.4x an observed-normal 88 s step,
# which trades a hang for a false kill on a slow-but-working install. Two attempts at 180 s with
# one pause is ~390 s per call, ~16 min, and 180 s is 2x the observed worst.
# **If three attempts are ever wanted, the honest route is shortening the STEP, not lengthening
# the bound - that is `(aeg)`, removing the apt call from the browser install entirely.**
set -uo pipefail

#: Seconds between the two attempts. See above: a pause, deliberately not a backoff ramp.
#:
#: ⚠ OVERRIDABLE FOR TESTS ONLY, and the reason is a real cost: the guard that exercises the
#: retry path pays this pause on every `make check`, which took the suite from ~18 s to 37 s
#: against a 45 s ceiling. A test proving the retry fires must not spend half the budget
#: sleeping. CI never sets it, so CI always gets the real 30.
PAUSE="${CI_BOUNDED_PAUSE:-30}"

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
echo "  Pausing ${PAUSE}s first - see the comment above for why this is NOT backoff." >&2
echo "" >&2
sleep "$PAUSE"

if attempt "$@"; then
  echo "ci_bounded: the retry succeeded. The first attempt was a hang, not a failure." >&2
  exit 0
else
  status=$?
fi
echo "ci_bounded: the retry also ended with exit ${status}. Failing the step." >&2
exit "$status"
