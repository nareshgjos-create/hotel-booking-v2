from langchain_core.tools import tool
from backend.services.hotel_service import check_hotel_availability as check_hotel_availability_service
from backend.utils.logger import logger
from datetime import datetime


@tool
def check_hotel_availability(
    hotel_id: int,
    check_in: str,
    check_out: str,
    guests: int
) -> str:
    """
    Check real hotel availability for a date range.

    Args:
        hotel_id: hotel ID
        check_in: YYYY-MM-DD
        check_out: YYYY-MM-DD
        guests: number of guests
    """

    logger.info(
        f"📅 Checking availability | hotel_id={hotel_id}, check_in={check_in}, check_out={check_out}, guests={guests}"
    )

    try:

        check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()

        result = check_hotel_availability_service(
            hotel_id=hotel_id,
            check_in=check_in_date,
            check_out=check_out_date,
            guests=guests
        )

        if not result["success"]:
            return f"❌ {result['message']}"

        room_types = result["available_room_types"]

        if not room_types:
            return f"""
⚠️ No rooms available

Hotel: {result['hotel_name']}
Location: {result['location']}
Stay: {result['check_in']} → {result['check_out']}
Guests: {result['guests']}

No room types available for these dates.
""".strip()

        lines = [
            "✅ Available Room Types",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Hotel: {result['hotel_name']}",
            f"Location: {result['location']}",
            f"Rating: {result['rating']}⭐",
            f"Stay: {result['check_in']} → {result['check_out']}",
            f"Guests: {result['guests']}",
            "",
            "Room Options:"
        ]

        for room in room_types:
            lines.append(
                f"""
{room['room_type']}
Capacity: {room['capacity']} guests
Price: ${room['price_per_night']} per night
Available: {room['available_rooms']} rooms
""".strip()
            )

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return f"❌ Error checking availability: {str(e)}"