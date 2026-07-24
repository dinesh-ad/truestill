"""Enable ``python -m vaeon_cli``."""

from __future__ import annotations

from vaeon_cli.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
