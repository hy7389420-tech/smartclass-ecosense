import argparse
import getpass
import os

from sqlalchemy import select

from app.database import session_scope
from app.models import User
from app.services.auth import hash_password


def create_admin(email: str, password: str) -> int:
    normalized_email = email.strip().lower()
    if "@" not in normalized_email or len(normalized_email) > 254:
        raise ValueError("Enter a valid email address.")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Admin password must contain 12 to 128 characters.")

    with session_scope() as session:
        if session.scalar(select(User.id).where(User.email == normalized_email)):
            raise ValueError("A user with this email already exists.")
        admin = User(
            email=normalized_email,
            password_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
        )
        session.add(admin)
        session.flush()
        return admin.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an administrator account.")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    args = parser.parse_args()
    if not args.email:
        parser.error("Provide --email or set ADMIN_EMAIL.")

    password = os.environ.get("ADMIN_PASSWORD")
    if password is None:
        password = getpass.getpass("Admin password (12+ characters): ")
        confirmation = getpass.getpass("Confirm admin password: ")
        if password != confirmation:
            parser.error("Passwords do not match.")

    try:
        admin_id = create_admin(args.email, password)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Administrator created: id={admin_id}, email={args.email.strip().lower()}")


if __name__ == "__main__":
    main()
