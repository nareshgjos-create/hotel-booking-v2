import json
from langchain_core.tools import tool

from backend.db.database import SessionLocal
from backend.db.models import PaymentRecord


@tool
def check_payment_status(invoice_number: str) -> str:
    """Check the payment status of an invoice by its invoice number.
    Returns payment status (paid/pending/overdue/partial), amount due,
    amount paid, due date, and payment date if available."""
    db = SessionLocal()
    try:
        record = (
            db.query(PaymentRecord)
            .filter(PaymentRecord.invoice_number == invoice_number)
            .first()
        )

        if not record:
            return json.dumps(
                {
                    "found": False,
                    "invoice_number": invoice_number,
                    "message": (
                        "Invoice number not found in payment records. "
                        "This may be a new or unregistered invoice."
                    ),
                }
            )

        return json.dumps(
            {
                "found": True,
                "invoice_number": record.invoice_number,
                "vendor_name": record.vendor_name,
                "payment_status": record.payment_status,
                "amount_due": record.amount_due,
                "amount_paid": record.amount_paid,
                "due_date": record.due_date,
                "payment_date": record.payment_date,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()
