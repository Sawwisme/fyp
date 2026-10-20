from sqlalchemy import select

from app.database import SessionLocal
from app.models import Clinic, ClinicAdministrator, User


def main() -> int:
    print("Approve a pending clinic administrator.")
    email = input("Applicant email: ").strip()

    try:
        with SessionLocal.begin() as db:
            applicant = db.scalar(
                select(User)
                .where(
                    User.email == email,
                    User.role == "clinic_administrator",
                    User.status == "pending",
                )
                .with_for_update()
            )

            if applicant is None:
                print("No pending administrator account found.")
                return 1

            membership = db.scalar(
                select(ClinicAdministrator)
                .where(
                    ClinicAdministrator.user_id == applicant.user_id,
                    ClinicAdministrator.membership_status == "pending",
                )
                .with_for_update()
            )

            if membership is None:
                print("No pending clinic membership found.")
                return 1

            clinic = db.scalar(
                select(Clinic)
                .where(
                    Clinic.clinic_id == membership.clinic_id,
                    Clinic.status.in_(["active", "pending"]),
                )
                .with_for_update()
            )

            if clinic is None:
                print("The selected clinic is unavailable for approval.")
                return 1

            print(f"Applicant: {applicant.full_name}")
            print(f"Email: {applicant.email}")
            print(f"Clinic: {clinic.clinic_name}")
            print(f"Clinic code: {clinic.clinic_code}")
            print(f"Clinic address: {clinic.address or 'Not provided'}")
            print(f"Clinic status: {clinic.status}")
            print(
                "Approval also activates the clinic if it is pending. "
                "Verify its identity and location before proceeding."
            )
            print()
            print(
                "Only approve after independently verifying that the "
                "applicant is authorized to manage this clinic."
            )

            confirmation = input("Type APPROVE to grant access: ").strip()

            if confirmation != "APPROVE":
                print("No changes made.")
                return 0

            clinic.status = "active"
            membership.membership_status = "approved"
            membership.clinic_name = clinic.clinic_name
            applicant.status = "active"

    except Exception as exc:
        print(f"Approval failed ({type(exc).__name__}).")
        return 1

    print("Approved. The administrator can now log in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())