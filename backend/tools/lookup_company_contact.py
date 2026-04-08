import json
from langchain_core.tools import tool

from backend.db.database import SessionLocal
from backend.db.models import CompanyContact


@tool
def lookup_company_contact(company_name: str) -> str:
    """Look up contact information for a company or vendor by name.
    Returns phone number, email, contact person, website, and address."""
    db = SessionLocal()
    try:
        search = f"%{company_name}%"

        record = (
            db.query(CompanyContact)
            .filter(CompanyContact.company_name.ilike(search))
            .first()
        )

        if not record:
            record = (
                db.query(CompanyContact)
                .filter(CompanyContact.alias.ilike(search))
                .first()
            )

        if not record:
            return json.dumps(
                {
                    "found": False,
                    "company_name": company_name,
                    "message": "Company not found in the contact directory.",
                }
            )

        return json.dumps(
            {
                "found": True,
                "company_name": record.company_name,
                "phone_number": record.phone_number,
                "email": record.email,
                "website": record.website,
                "contact_person": record.contact_person,
                "address": record.address,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()
