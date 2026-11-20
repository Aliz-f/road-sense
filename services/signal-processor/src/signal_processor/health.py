from __future__ import annotations

import sys

from .config import ProcessorConfig


def main() -> int:
    try:
        return 0 if ProcessorConfig.from_environment().ready_file.is_file() else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
