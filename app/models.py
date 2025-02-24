from sqlalchemy import create_engine, Column, String, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://venkat:admin@postgres:5432/image_processing"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Request(Base):
    __tablename__ = "requests"
    request_id = Column(String, primary_key=True)
    status = Column(String)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String)
    product_name = Column(String)
    input_image_urls = Column(String)
    output_image_urls = Column(String)
    request_id = Column(String, ForeignKey("requests.request_id"))

Base.metadata.create_all(bind=engine)