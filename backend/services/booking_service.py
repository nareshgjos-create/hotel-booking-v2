import uuid
from datetime import datetime

from backend.db.database import SessionLocal
from backend.db.models import Booking, RoomType, Hotel
from backend.services.hotel_service import check_hotel_availability


def create_booking_service(
    hotel_id: int,
    check_in: str,
    check_out: str,
    guests: int,
    user_name: str,
    user_email: str,
    room_type: str = None,
    payment_transaction_id: str = None,
):
    db = SessionLocal()

    try:
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()

        # Check availability
        availability = check_hotel_availability(
            hotel_id=hotel_id,
            check_in=check_in_date,
            check_out=check_out_date,
            guests=guests,
        )

        if not availability["success"]:
            return {"success": False, "message": availability["message"]}

        available_rooms = availability["available_room_types"]

        if not available_rooms:
            return {"success": False, "message": "No rooms available for selected dates."}

        # Select room type
        if room_type:
            selected_room = next(
                (r for r in available_rooms if r["room_type"].lower() == room_type.lower()),
                None,
            )
            if not selected_room:
                available_names = [r["room_type"] for r in available_rooms]
                return {
                    "success": False,
                    "message": (
                        f"Room type '{room_type}' is not available for these dates. "
                        f"Available: {', '.join(available_names)}."
                    ),
                }
        else:
            selected_room = available_rooms[0]

        booking_reference = f"BK-{uuid.uuid4().hex[:8].upper()}"
        nights = (check_out_date - check_in_date).days
        booked_price_per_night = selected_room["price_per_night"]
        total_price = nights * booked_price_per_night

        booking = Booking(
            booking_reference=booking_reference,
            hotel_id=hotel_id,
            room_type_id=selected_room["room_type_id"],
            user_name=user_name,
            user_email=user_email,
            check_in=check_in_date,
            check_out=check_out_date,
            guests=guests,
            booked_price_per_night=booked_price_per_night,
            total_price=total_price,
            currency="GBP",
            status="confirmed",
            payment_transaction_id=payment_transaction_id,
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        return {
            "success": True,
            "booking_reference": booking_reference,
            "hotel_name": availability["hotel_name"],
            "room_type": selected_room["room_type"],
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "booked_price_per_night": booked_price_per_night,
            "total_price": total_price,
            "currency": "GBP",
            "status": "confirmed",
            "payment_transaction_id": payment_transaction_id,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}

    finally:
        db.close()
