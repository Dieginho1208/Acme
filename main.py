#!/usr/bin/env python3
"""Start Acme Logistics Suite.

If the database does not exist yet, the demo database is generated first, so a
fresh clone runs with a single command::

    python main.py
"""

import argparse
import sys
from pathlib import Path

from acme.config import default_db_path


def main(argv=None) -> int:
    """Parse arguments, make sure the database exists and open the window."""
    parser = argparse.ArgumentParser(description="Acme Logistics Suite")
    parser.add_argument("--db", type=Path, default=default_db_path(),
                        help="SQLite database file (default: %(default)s)")
    args = parser.parse_args(argv)

    if not args.db.exists():
        import setup_mock_db
        print(f"{args.db} not found: generating the demo database first.")
        setup_mock_db.main(["--path", str(args.db), "--force"])

    from acme.core.context import AppContext
    from acme.ui.app import Application

    Application(AppContext(args.db)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
