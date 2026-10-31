import argparse
import getpass

from sqlalchemy import select

from app.database import session_scope
from app.models import User
from app.services.auth import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a local administrator password.")
    parser.add_argument("email", help="Administrator email address.")
    args = parser.parse_args()

    password = getpass.getpass("New admin password (12+ characters): ")
    confirmation = getpass.getpass("Confirm new admin password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    if len(password) < 12 or len(password) > 128:
        parser.error("Admin password must be 12 to 128 characters.")

    normalized_email = args.email.strip().lower()
    with session_scope() as session:
        admin = session.scalar(
            select(User).where(User.email == normalized_email, User.role == "ADMIN")
        )
        if admin is None:
            parser.error("Administrator account was not found.")
        admin.password_hash = hash_password(password)
        admin.token_version += 1

    print(f"Password reset complete for {normalized_email}.")


if __name__ == "__main__":
    main()
