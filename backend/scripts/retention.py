import argparse
import json

from app.database import session_scope
from app.services.reports import run_retention


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or execute the configured backend data-retention policy."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete expired rows. Without this option, only preview counts.",
    )
    args = parser.parse_args()
    with session_scope() as session:
        result = run_retention(session, actor_user_id=None, dry_run=not args.execute)
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
