from celery import Celery
from app.models import Request, Product, SessionLocal
from PIL import Image
import requests
from io import BytesIO
import uuid
import os
import logging
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Initialize Celery
celery_app = Celery('tasks', broker='redis://redis:6379/0')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name="dznrmbb65",
    api_key="598118775672361",
    api_secret="AMSJ9ZcVK2-kOFMbxrRZwWhEDBA",  # Replace with your actual API secret
    secure=True
)

@celery_app.task(name="process_images")
def process_images(request_id, rows):
    db = SessionLocal()
    try:
        # Update request status to "Processing"
        db_request = db.query(Request).filter(Request.request_id == request_id).first()
        if not db_request:
            logger.error(f"Request {request_id} not found in the database.")
            raise ValueError(f"Request {request_id} not found.")

        db_request.status = "Processing"
        db.commit()

        # Process each row in the CSV
        for row in rows:
            try:
                # Validate the row
                print(row)
                # if len(row) != 3:
                #     logger.warning(f"Skipping invalid row: {row}. Expected 3 columns, found {len(row)}.")
                #     continue
                row[-1] = row[-1].strip('"')  # Remove extra double quotes

                # Step 2: Extract serial_number, product_name, and image_urls
                serial_number = row[0]  # First value -> serial_number
                product_name = row[1]   # Second value -> product_name
                image_urls = row[2:]    # Rest all -> image_urls

                # Step 3: Clean up image URLs (remove leading/trailing spaces)
                image_urls = [url.strip() for url in image_urls]
                # serial_number, product_name, input_image_urls = row
                # input_urls = [url.strip() for url in image_urls.split(",")]
                output_urls = []

                for url in image_urls:
                    try:
                        # Download the image
                        response = requests.get(url)
                        response.raise_for_status()  # Raise an error for bad status codes

                        # Open and compress the image
                        img = Image.open(BytesIO(response.content))
                        img = img.resize((img.width // 2, img.height // 2))  # Resize by 50%

                        # Save the compressed image to a temporary file
                        temp_filename = f"{uuid.uuid4()}.jpg"
                        img.save(temp_filename, format="JPEG", quality=50)

                        # Upload the image to Cloudinary
                        upload_result = cloudinary.uploader.upload(temp_filename)
                        cloudinary_url = upload_result["secure_url"]

                        # Save the Cloudinary URL
                        output_urls.append(cloudinary_url)

                        # Remove the temporary file
                        os.remove(temp_filename)

                    except requests.exceptions.RequestException as e:
                        logger.error(f"Failed to download image from {url}: {e}")
                        # continue
                    except Exception as e:
                        logger.error(f"Error processing image from {url}: {e}")
                        # continue

                # Save product data to the database
                db_product = Product(
                    serial_number=serial_number,
                    product_name=product_name,
                    input_image_urls=image_urls,
                    output_image_urls=",".join(output_urls),
                    request_id=request_id
                )
                db.add(db_product)
                db.commit()

            except Exception as e:
                logger.error(f"Error processing row {row}: {e}")
                db.rollback()  # Rollback the transaction in case of an error

        # Update request status to "Completed"
        db_request.status = "Completed"
        db.commit()

    except Exception as e:
        # Update request status to "Failed"
        if db_request:
            db_request.status = "Failed"
            db.commit()
        logger.error(f"Task failed for request {request_id}: {e}")
        raise  # Re-raise the exception to mark the task as failed

    finally:
        # Close the database session
        db.close()