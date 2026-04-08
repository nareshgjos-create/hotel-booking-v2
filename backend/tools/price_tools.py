from langchain.tools import tool

from backend.services.price_service import calculate_price_service


@tool
def calculate_price(
    hotel_id: int,
    room_type: str,
    check_in: str,
    check_out: str,
    guests: int,
) -> str:
    """
    Calculate the total price for a hotel booking before payment.
    Returns a price breakdown including price per night, number of nights, and total cost.
    """
    result = calculate_price_service(
        hotel_id=hotel_id,
        room_type=room_type,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
    )

    if not result["success"]:
        return f"❌ Price calculation failed: {result['message']}"

    return (
        f"💰 Price Breakdown for {result['hotel_name']}:\n"
        f"  Room type      : {result['room_type']}\n"
        f"  Price per night: £{result['price_per_night']:.2f}\n"
        f"  Nights         : {result['nights']} "
        f"({result['check_in']} → {result['check_out']})\n"
        f"  Guests         : {result['guests']}\n"
        f"  ─────────────────────────────\n"
        f"  Total          : £{result['total_price']:.2f} {result['currency']}"
    )
