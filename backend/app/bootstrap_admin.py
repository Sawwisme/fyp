from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import ClinicAdministrator, User
from app.schemas.auth import OwnerRegister
from app.services.auth_service import hash_password


def main() -> int:
    print("Create the first VetDental clinic administrator.")

    full_name = input("Full name: ").strip()
    email = input("Email: ").strip()
    clinic_name = input("Clinic name: ").strip()
    phone = input("Phone number (optional): ").strip()

    password = getpass("Password (at least 8 characters): ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        print("Passwords do not match.")
        return 1

    if not clinic_name or len(clinic_name) > 150:
        print("Clinic name must contain between 1 and 150 characters.")
        return 1

    try:
        # Reuse the existing name, email, phone and password validation.
        details = OwnerRegister(
            full_name=full_name,
            email=email,
            password=password,
            phone_number=phone or None,
        )
    except ValidationError as exc:
        for error in exc.errors(include_input=False):
            field = ".".join(str(part) for part in error["loc"])
            print(f"{field}: {error['msg']}")
        return 1

    try:
        with SessionLocal.begin() as db:
            existing_admin = db.scalar(
                select(ClinicAdministrator.clinic_administrator_id)
                .limit(1)
            )

            if existing_admin is not None:
                print("An administrator profile already exists.")
                return 1

            existing_user = db.scalar(
                select(User.user_id).where(
                    User.email == str(details.email)
                )
            )

            if existing_user is not None:
                print("That email already belongs to an account.")
                print("Use a different email; existing roles are not changed.")
                return 1

            user = User(
                full_name=details.full_name,
                email=str(details.email),
                phone_number=details.phone_number,
                password_hash=hash_password(
                    details.password.get_secret_value()
                ),
                role="clinic_administrator",
                status="active",
            )

            user.clinic_administrator = ClinicAdministrator(
                clinic_name=clinic_name,
            )

            db.add(user)

    except IntegrityError:
        print("Account creation failed because a database constraint was hit.")
        return 1

    print("Administrator created. You can now use the staff login page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())