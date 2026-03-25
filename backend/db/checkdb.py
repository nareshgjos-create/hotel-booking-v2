from backend.db.database import SessionLocal
from backend.db.models import Hotel, RoomType, Booking

db = SessionLocal()

print("Hotels:", db.query(Hotel).count())
print("Room Types:", db.query(RoomType).count())
print("Bookings:", db.query(Booking).count())

print("\nSample Hotels:")
for h in db.query(Hotel).limit(5):
    print(h.name, h.location)

print("\nSample Room Types:")
for r in db.query(RoomType).limit(5):
    print(r.name, r.total_rooms)

print("\nSample Bookings:")
for b in db.query(Booking).limit(5):
    print(b.booking_reference)

db.close()