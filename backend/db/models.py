from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Date,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.db.database import Base


class Hotel(Base):
    """
    Main hotel entity.
    Stores hotel-level information only.
    """
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    location = Column(String, nullable=False, index=True)
    amenities = Column(String, nullable=True)
    rating = Column(Float, default=0.0, nullable=False)

    room_types = relationship(
        "RoomType",
        back_populates="hotel",
        cascade="all, delete-orphan",
    )

    bookings = relationship(
        "Booking",
        back_populates="hotel",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Hotel id={self.id} name='{self.name}' location='{self.location}'>"


class RoomType(Base):
    """
    Inventory definition per hotel.
    Example: Standard, Deluxe, Suite.
    """
    __tablename__ = "room_types"

    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    price_per_night = Column(Float, nullable=False)
    total_rooms = Column(Integer, nullable=False)

    hotel = relationship("Hotel", back_populates="room_types")

    bookings = relationship(
        "Booking",
        back_populates="room_type",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_room_type_per_hotel"),
        CheckConstraint("capacity > 0", name="ck_room_type_capacity_positive"),
        CheckConstraint("price_per_night >= 0", name="ck_room_type_price_non_negative"),
        CheckConstraint("total_rooms >= 0", name="ck_room_type_total_rooms_non_negative"),
    )

    def __repr__(self):
        return (
            f"<RoomType id={self.id} hotel_id={self.hotel_id} "
            f"name='{self.name}' capacity={self.capacity} total_rooms={self.total_rooms}>"
        )


class Booking(Base):
    """
    Booking record.
    Availability will be derived from:
    total_rooms - overlapping confirmed bookings
    """
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_reference = Column(String, nullable=False, unique=True, index=True)

    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False, index=True)
    room_type_id = Column(Integer, ForeignKey("room_types.id"), nullable=False, index=True)

    user_name = Column(String, nullable=False)
    user_email = Column(String, nullable=False, index=True)

    check_in = Column(Date, nullable=False, index=True)
    check_out = Column(Date, nullable=False, index=True)
    guests = Column(Integer, nullable=False)

    status = Column(String, nullable=False, default="confirmed", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    hotel = relationship("Hotel", back_populates="bookings")
    room_type = relationship("RoomType", back_populates="bookings")

    __table_args__ = (
        CheckConstraint("guests > 0", name="ck_booking_guests_positive"),
    )

    def __repr__(self):
        return (
            f"<Booking id={self.id} ref='{self.booking_reference}' "
            f"hotel_id={self.hotel_id} room_type_id={self.room_type_id} "
            f"check_in={self.check_in} check_out={self.check_out} status='{self.status}'>"
        )