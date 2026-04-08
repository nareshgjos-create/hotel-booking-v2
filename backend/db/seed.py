import sys
import os
from datetime import date

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.db.database import Base, engine, SessionLocal
from backend.db.models import Hotel, RoomType, Booking


def seed():
    """
    Creates all tables and fills with sample hotel + room types + bookings data.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created!")

    db = SessionLocal()

    try:
        if db.query(Hotel).count() > 0:
            print("Already seeded!")
            print("Hotels in DB:", db.query(Hotel).count())
            print("Room types in DB:", db.query(RoomType).count())
            print("Bookings in DB:", db.query(Booking).count())
            return

        hotels = [
            Hotel(
                name="The Grand Palace",
                location="London",
                amenities="WiFi,Pool,Gym,Spa",
                rating=4.8,
            ),
            Hotel(
                name="City Lights Inn",
                location="London",
                amenities="WiFi,Breakfast",
                rating=4.2,
            ),
            Hotel(
                name="Sunset Resort",
                location="Paris",
                amenities="WiFi,Pool,Restaurant",
                rating=4.5,
            ),
            Hotel(
                name="Budget Stay",
                location="Paris",
                amenities="WiFi",
                rating=3.8,
            ),
            Hotel(
                name="Ocean View Hotel",
                location="Barcelona",
                amenities="WiFi,Pool,Beach Access",
                rating=4.7,
            ),
            Hotel(
                name="The Royal Inn",
                location="Barcelona",
                amenities="WiFi,Gym,Restaurant",
                rating=4.3,
            ),
            Hotel(
                name="Mountain Retreat",
                location="Dubai",
                amenities="WiFi,Pool,Spa,Gym",
                rating=4.9,
            ),
            Hotel(
                name="Downtown Suites",
                location="Dubai",
                amenities="WiFi,Breakfast,Parking",
                rating=4.0,
            ),
        ]

        db.add_all(hotels)
        db.commit()

        for hotel in hotels:
            db.refresh(hotel)

        room_types = [
            # London - The Grand Palace
            RoomType(hotel_id=hotels[0].id, name="Standard", capacity=2, price_per_night=220.0, total_rooms=12),
            RoomType(hotel_id=hotels[0].id, name="Deluxe", capacity=3, price_per_night=300.0, total_rooms=6),
            RoomType(hotel_id=hotels[0].id, name="Suite", capacity=4, price_per_night=420.0, total_rooms=2),

            # London - City Lights Inn
            RoomType(hotel_id=hotels[1].id, name="Standard", capacity=2, price_per_night=110.0, total_rooms=10),
            RoomType(hotel_id=hotels[1].id, name="Deluxe", capacity=3, price_per_night=150.0, total_rooms=3),

            # Paris - Sunset Resort
            RoomType(hotel_id=hotels[2].id, name="Standard", capacity=2, price_per_night=170.0, total_rooms=8),
            RoomType(hotel_id=hotels[2].id, name="Deluxe", capacity=3, price_per_night=220.0, total_rooms=5),
            RoomType(hotel_id=hotels[2].id, name="Suite", capacity=4, price_per_night=320.0, total_rooms=1),

            # Paris - Budget Stay
            RoomType(hotel_id=hotels[3].id, name="Standard", capacity=2, price_per_night=65.0, total_rooms=15),

            # Barcelona - Ocean View Hotel
            RoomType(hotel_id=hotels[4].id, name="Standard", capacity=2, price_per_night=190.0, total_rooms=7),
            RoomType(hotel_id=hotels[4].id, name="Deluxe", capacity=3, price_per_night=250.0, total_rooms=4),
            RoomType(hotel_id=hotels[4].id, name="Suite", capacity=4, price_per_night=360.0, total_rooms=2),

            # Barcelona - The Royal Inn
            RoomType(hotel_id=hotels[5].id, name="Standard", capacity=2, price_per_night=145.0, total_rooms=9),
            RoomType(hotel_id=hotels[5].id, name="Deluxe", capacity=3, price_per_night=190.0, total_rooms=2),

            # Dubai - Mountain Retreat
            RoomType(hotel_id=hotels[6].id, name="Standard", capacity=2, price_per_night=280.0, total_rooms=14),
            RoomType(hotel_id=hotels[6].id, name="Deluxe", capacity=3, price_per_night=350.0, total_rooms=8),
            RoomType(hotel_id=hotels[6].id, name="Suite", capacity=5, price_per_night=500.0, total_rooms=3),

            # Dubai - Downtown Suites
            RoomType(hotel_id=hotels[7].id, name="Standard", capacity=2, price_per_night=95.0, total_rooms=11),
            RoomType(hotel_id=hotels[7].id, name="Deluxe", capacity=3, price_per_night=130.0, total_rooms=4),
        ]

        db.add_all(room_types)
        db.commit()

        for room_type in room_types:
            db.refresh(room_type)

        sample_bookings = [
            Booking(
                booking_reference="BK-LON001",
                hotel_id=hotels[0].id,
                room_type_id=room_types[0].id,
                user_name="Alice Smith",
                user_email="alice@example.com",
                check_in=date(2026, 4, 21),
                check_out=date(2026, 4, 25),
                guests=2,
                booked_price_per_night=220.0,
                total_price=880.0,
                currency="GBP",
                status="confirmed",
            ),
            Booking(
                booking_reference="BK-LON002",
                hotel_id=hotels[0].id,
                room_type_id=room_types[0].id,
                user_name="Bob Jones",
                user_email="bob@example.com",
                check_in=date(2026, 4, 22),
                check_out=date(2026, 4, 27),
                guests=2,
                booked_price_per_night=220.0,
                total_price=880.0,
                currency="GBP",
                status="confirmed",
            ),
            Booking(
                booking_reference="BK-PAR001",
                hotel_id=hotels[2].id,
                room_type_id=room_types[6].id,
                user_name="Claire Martin",
                user_email="claire@example.com",
                check_in=date(2026, 5, 1),
                check_out=date(2026, 5, 5),
                guests=2,
                booked_price_per_night=220.0,
                total_price=880.0,
                currency="GBP",
                status="confirmed",
            ),
            Booking(
                booking_reference="BK-DXB001",
                hotel_id=hotels[6].id,
                room_type_id=room_types[15].id,
                user_name="David Khan",
                user_email="david@example.com",
                check_in=date(2026, 4, 21),
                check_out=date(2026, 4, 30),
                guests=3,
                booked_price_per_night=350.0,
                total_price=3150.0,
                currency="GBP",
                status="confirmed",
            ),
        ]

        db.add_all(sample_bookings)
        db.commit()

        print(f"✅ Seeded {len(hotels)} hotels successfully!")
        print(f"✅ Seeded {len(room_types)} room types successfully!")
        print(f"✅ Seeded {len(sample_bookings)} bookings successfully!")

        print("Hotels in DB:", db.query(Hotel).count())
        print("Room types in DB:", db.query(RoomType).count())
        print("Bookings in DB:", db.query(Booking).count())

    finally:
        db.close()


if __name__ == "__main__":
    seed()