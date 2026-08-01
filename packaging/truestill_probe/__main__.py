"""Two modes in one artifact: measure and exit, or run the real app.

One binary rather than two because the *layout* is what is being measured, and two separately
built artifacts could differ in exactly the way the measurement is about. The app mode is what
assertions 3 and 4 need - the job launches it, waits for the session URL file, and makes an HTTP
request - and those have to be checked from outside, since a windowed process cannot report them.
"""

from __future__ import annotations

import sys
from pathlib import Path

from truestill_app.__main__ import main as run_app

from truestill_probe import write_findings

_PROBE_FLAG = "--probe"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _PROBE_FLAG in args:
        index = args.index(_PROBE_FLAG)
        write_findings(Path(args[index + 1]))
        return 0

    return run_app(args)


if __name__ == "__main__":
    raise SystemExit(main())
