from langchain_core.tools import tool
from backend.services.hotel_service import get_hotels_by_location
from backend.utils.logger import logger


@tool
def search_hotels(location: str) -> str:
    """
    Search for hotels in a given location/city.
    Use this when the user asks to find hotels somewhere.
    """

    logger.info(f"🔍 Searching hotels in: {location}")

    try:
        hotels = get_hotels_by_location(location)

        if not hotels:
            return f"❌ No hotels found in {location}. Try another city."

        result = f"🏨 Found {len(hotels)} hotel(s) in {location}:\n\n"

        for h in hotels:
            result += (
                f"\nHotel ID  : {h.id}\n"
                f"Name      : {h.name}\n"
                f"Location  : {h.location}\n"
                f"Rating    : {h.rating}⭐\n"
                f"Amenities : {h.amenities}\n"
                f"{'─' * 40}\n"
            )

        return result.strip()

    except Exception as e:
        logger.error(f"Error searching hotels: {e}")
        return f"❌ Error searching hotels: {str(e)}"