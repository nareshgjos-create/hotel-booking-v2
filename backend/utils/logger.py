from loguru import logger
import sys
import os

# Create logs folder if not exists
os.makedirs("logs", exist_ok=True)

# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)

# Add file logger
logger.add(
    "logs/app.log",
    rotation="1 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
)

# Separate auth log — captures registration, login, and token events
logger.add(
    "logs/auth.log",
    rotation="1 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    filter=lambda record: any(
        kw in record["message"].lower()
        for kw in ["register", "login", "auth", "token", "user logged", "failed login"]
    ),
)