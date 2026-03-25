from backend.db.database import SessionLocal
from backend.db.models import Availability

db = SessionLocal()

rows = db.query(Availability).all()

for r in rows:
    #print(r.id, r.hotel_id, r.room_type, r.available_rooms)
    print("Let's check availability for hotel_id:")
    print(r.hotel_id, r.room_type, r.available_rooms)

db.close()