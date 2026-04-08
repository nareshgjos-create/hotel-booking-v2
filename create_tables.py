from backend.db.database import Base, engine
from backend.db import models
from backend.db import auth_models  # User table for registration/login

Base.metadata.create_all(bind=engine)

print("Tables created successfully.")