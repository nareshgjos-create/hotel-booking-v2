from datetime import date
from backend.db.database import SessionLocal
from backend.db.models import Hotel, RoomType, Booking


def get_hotels_by_location(location: str):
    db = SessionLocal()
    try:
        hotels = db.query(Hotel).filter(
            Hotel.location.ilike(f"%{location}%")
        ).all()
        return hotels
    finally:
        db.close()


def check_hotel_availability(
    hotel_id: int,
    check_in: date,
    check_out: date,
    guests: int
):
    """
    Real availability check per room type:
    - check overlapping bookings
    - calculate remaining inventory
    - filter by guest capacity
    """

    db = SessionLocal()

    try:
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

        if not hotel:
            return {
                "success": False,
                "message": f"Hotel with ID {hotel_id} not found."
            }

        if check_in >= check_out:
            return {
                "success": False,
                "message": "Check-out must be after check-in"
            }

        if guests <= 0:
            return {
                "success": False,
                "message": "Guests must be at least 1"
            }

        room_types = db.query(RoomType).filter(
            RoomType.hotel_id == hotel_id
        ).all()

        availability = []

        for room in room_types:

            overlapping = db.query(Booking).filter(
                Booking.room_type_id == room.id,
                Booking.status == "confirmed",
                Booking.check_in < check_out,
                Booking.check_out > check_in
            ).count()

            available_rooms = room.total_rooms - overlapping

            if available_rooms > 0 and room.capacity >= guests:
                availability.append({
                    "room_type_id": room.id,
                    "room_type": room.name,
                    "capacity": room.capacity,
                    "price_per_night": room.price_per_night,
                    "total_rooms": room.total_rooms,
                    "booked_rooms": overlapping,
                    "available_rooms": available_rooms
                })

        return {
            "success": True,
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "location": hotel.location,
            "rating": hotel.rating,
            "amenities": hotel.amenities,
            "check_in": str(check_in),
            "check_out": str(check_out),
            "guests": guests,
            "available_room_types": availability
        }

    finally:
        db.close()