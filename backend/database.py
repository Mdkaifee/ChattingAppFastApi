import os
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()                                                                        #Loads variables from a .env file (like DB password, host, etc.).
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASSWORD")

# Encode special characters in the password
encoded_pass = urllib.parse.quote_plus(DB_PASS)                                        #If your password has special characters (like @, #, !), this step makes it safe to include in a URL.

SQLALCHEMY_DATABASE_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{encoded_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"   #This puts all the connection info together into one URL.
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"charset": "utf8mb4"})   #how to connect and talk to the database.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
