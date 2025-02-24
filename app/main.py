from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
import uuid
import csv
from celery import Celery
from app.models import Request, Product, SessionLocal
from io import StringIO

# Initialize FastAPI app
app = FastAPI()

# Serve processed images as static files
app.mount("/processed_images", StaticFiles(directory="/app/processed_images"), name="processed_images")

# Celery configuration
celery_app = Celery('tasks', broker='redis://redis:6379/0')

# Upload API
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    # Generate a unique request ID
    request_id = str(uuid.uuid4())

    # Read and decode the CSV file
    contents = await file.read()
    decoded_contents = contents.decode("utf-8")

    # Debugging: Print raw CSV data
    print("Raw CSV Data:")
    print(decoded_contents)

    # Clean the CSV data by removing outer quotes from each line
    cleaned_lines = []
    for line in decoded_contents.splitlines():
        if line.startswith('"') and line.endswith('"'):
            line = line[1:-1]  # Remove the outer quotes
        cleaned_lines.append(line)

    # Join the cleaned lines back into a single string
    cleaned_csv = "\n".join(cleaned_lines)

    # Create a file-like object from the cleaned CSV data
    file_like_object = StringIO(cleaned_csv)

    # Use csv.reader to parse the CSV
    reader = csv.reader(file_like_object, delimiter=",", quotechar='"')

    # Read the headers
    headers = next(reader)

    # Strip extra spaces from headers
    headers = [header.strip() for header in headers]

    # Debugging: Print stripped headers
    print(f"Stripped Headers: {headers}")

    # Validate headers
    if headers != ["S. No.", "Product Name", "Input Image Urls"]:
        raise HTTPException(status_code=400, detail="Invalid CSV format")

    # Save request to the database
    db = SessionLocal()
    db_request = Request(request_id=request_id, status="Pending")
    db.add(db_request)
    db.commit()

    # Enqueue the Celery task for processing
    celery_app.send_task("process_images", args=[request_id, list(reader)])

    return {
        "request_id": request_id,
        "status": "Pending",
        "message": "CSV file accepted for processing."
    }

# Status API
@app.get("/status/{request_id}")
async def get_status(request_id: str):
    db = SessionLocal()
    db_request = db.query(Request).filter(Request.request_id == request_id).first()
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_id": request_id, "status": db_request.status}