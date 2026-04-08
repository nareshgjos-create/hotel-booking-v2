from datetime import datetime

from backend.db.database import SessionLocal
from backend.db.models import Hotel, RoomType


def calculate_price_service(
    hotel_id: int,
    room_type: str,
    check_in: str,
    check_out: str,
    guests: int,
) -> dict:
    db = SessionLocal()
    try:
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
        nights = (check_out_date - check_in_date).days

        if nights <= 0:
            return {"success": False, "message": "Check-out must be after check-in."}

        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            return {"success": False, "message": f"Hotel with ID {hotel_id} not found."}

        room = (
            db.query(RoomType)
            .filter(RoomType.hotel_id == hotel_id, RoomType.name.ilike(room_type))
            .first()
        )

        if not room:
            available = db.query(RoomType).filter(RoomType.hotel_id == hotel_id).all()
            types = [r.name for r in available]
            return {
                "success": False,
                "message": (
                    f"Room type '{room_type}' not found at {hotel.name}. "
                    f"Available types: {', '.join(types)}. Please choose one."
                ),
            }

        if room.capacity < guests:
            return {
                "success": False,
                "message": (
                    f"The {room.name} room holds up to {room.capacity} guests "
                    f"but you requested {guests}. Please choose a larger room type."
                ),
            }

        total_price = nights * room.price_per_night

        return {
            "success": True,
            "hotel_name": hotel.name,
            "room_type": room.name,
            "price_per_night": room.price_per_night,
            "nights": nights,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "total_price": total_price,
            "currency": "GBP",
        }

    finally:
        db.close()
