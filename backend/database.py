import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()

# Build database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "RAG_DB")

    auth = f"{db_user}:{db_password}" if db_password else db_user
    DATABASE_URL = f"postgresql://{auth}@{db_host}:{db_port}/{db_name}"

# SQLAlchemy Engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Automatically reconnect if connection is dropped
)

# SQLAlchemy SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """Dependency that yields a database session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """Test PostgreSQL database connection."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT current_database(), current_user;")).fetchone()
        return {
            "database": result[0],
            "user": result[1],
            "status": "connected",
        }
