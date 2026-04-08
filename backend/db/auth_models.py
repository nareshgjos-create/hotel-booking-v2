from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from backend.db.database import Base


class User(Base):
    """
    User account for registration and login.
    is_active: 1 = active, 0 = disabled
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<User id={self.id} email='{self.email}'>"
