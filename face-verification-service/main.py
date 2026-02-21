from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import face_recognition
import io
from PIL import Image
import numpy as np
from typing import Dict
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Face Verification API",
    description="Compare faces between ID documents and selfies for identity verification",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration - Allow your Django API to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://api.cafatickets.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration constants
VERIFICATION_THRESHOLD = 0.6  # Face distance threshold (lower = stricter)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def validate_image(file: UploadFile) -> bytes:
    """
    Validate uploaded image file
    
    Args:
        file: Uploaded file from request
        
    Returns:
        bytes: File contents
        
    Raises:
        HTTPException: If validation fails
    """
    # Check file extension
    if file.filename:
        ext = file.filename.split('.')[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
    
    # Read and check file size
    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    # Validate it's a real image
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()  # Verify it's actually an image
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or corrupted image file: {str(e)}"
        )
    
    file.file.seek(0)  # Reset file pointer
    return contents


def extract_face_encoding(image_bytes: bytes, image_name: str = "image", is_id_document: bool = False):
    """
    Extract face encoding from image
    
    Args:
        image_bytes: Image file contents
        image_name: Name for logging purposes
        is_id_document: If True, will select largest face when multiple detected (for ID cards with duplicate photos)
        
    Returns:
        tuple: (encoding array, error message)
    """
    try:
        # Load image
        image = face_recognition.load_image_file(io.BytesIO(image_bytes))
        
        # Find face locations
        face_locations = face_recognition.face_locations(image, model="hog")
        
        if len(face_locations) == 0:
            logger.warning(f"No face detected in {image_name}")
            return None, "No face detected in image. Please ensure your face is clearly visible."
        
        if len(face_locations) > 1:
            if is_id_document:
                # For ID documents, select the largest face (main photo)
                # Calculate face size (area) for each detected face
                face_sizes = []
                for face_location in face_locations:
                    top, right, bottom, left = face_location
                    width = right - left
                    height = bottom - top
                    area = width * height
                    face_sizes.append(area)
                
                # Get index of largest face
                largest_face_idx = face_sizes.index(max(face_sizes))
                largest_face = face_locations[largest_face_idx]
                
                logger.info(f"Multiple faces detected in {image_name} ({len(face_locations)} faces). Selected largest face for ID verification.")
                
                # Get encoding for only the largest face
                encodings = face_recognition.face_encodings(image, [largest_face])
                
                if len(encodings) == 0:
                    logger.error(f"Could not encode largest face in {image_name}")
                    return None, "Could not process face. Please use a clearer photo."
                
                logger.info(f"Successfully extracted face encoding from largest face in {image_name}")
                return encodings[0], None
            else:
                # For selfies, we want exactly one face
                logger.warning(f"Multiple faces detected in {image_name}: {len(face_locations)} faces")
                return None, f"Multiple faces detected ({len(face_locations)}). Please use an image with only one face."
        
        # Single face detected - normal processing
        encodings = face_recognition.face_encodings(image, face_locations)
        
        if len(encodings) == 0:
            logger.error(f"Could not encode face in {image_name}")
            return None, "Could not process face. Please use a clearer photo."
        
        logger.info(f"Successfully extracted face encoding from {image_name}")
        return encodings[0], None
        
    except Exception as e:
        logger.error(f"Error extracting face from {image_name}: {str(e)}")
        return None, f"Error processing image: {str(e)}"


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "service": "Face Verification API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "verify": "/verify-face"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test that face_recognition is working
        test_array = np.zeros((100, 100, 3), dtype=np.uint8)
        _ = face_recognition.face_locations(test_array)
        
        return {
            "status": "healthy",
            "service": "face-verification-api",
            "face_recognition_available": True,
            "threshold": VERIFICATION_THRESHOLD
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/verify-face")
async def verify_face(
    id_document: UploadFile = File(..., description="ID document/card image with face"),
    selfie: UploadFile = File(..., description="Selfie image to verify against ID")
) -> Dict:
    """
    Verify if the face in the selfie matches the face in the ID document
    
    **Process:**
    1. Validates both images
    2. Detects and extracts face from ID document (selects largest if multiple)
    3. Detects and extracts face from selfie (must be single face)
    4. Compares the two faces
    5. Returns match result with confidence score
    
    **Returns:**
    - `success`: Operation success status
    - `verified`: Whether the faces match (bool)
    - `confidence`: Match confidence 0-1 (higher = more confident match)
    - `distance`: Face distance metric (lower = more similar)
    - `threshold`: Threshold used for verification
    - `message`: Human-readable result message
    
    **Raises:**
    - 400: Invalid image, no face detected, or multiple faces in selfie
    - 500: Internal processing error
    """
    logger.info(f"Verification request - ID: {id_document.filename}, Selfie: {selfie.filename}")
    
    try:
        # Step 1: Validate images
        logger.info("Validating uploaded images...")
        id_bytes = validate_image(id_document)
        selfie_bytes = validate_image(selfie)
        
        # Step 2: Extract face from ID document (allow multiple faces, select largest)
        logger.info("Extracting face from ID document...")
        id_encoding, id_error = extract_face_encoding(id_bytes, "ID document", is_id_document=True)
        if id_error:
            logger.warning(f"ID document processing failed: {id_error}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "id_document",
                    "message": id_error
                }
            )
        
        # Step 3: Extract face from selfie (require single face)
        logger.info("Extracting face from selfie...")
        selfie_encoding, selfie_error = extract_face_encoding(selfie_bytes, "selfie", is_id_document=False)
        if selfie_error:
            logger.warning(f"Selfie processing failed: {selfie_error}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "selfie",
                    "message": selfie_error
                }
            )
        
        # Step 4: Compare faces
        logger.info("Comparing faces...")
        distance = float(face_recognition.face_distance([id_encoding], selfie_encoding)[0])
        verified = distance < VERIFICATION_THRESHOLD
        confidence = float(1 - distance)
        
        # Determine message based on result
        if verified:
            if confidence >= 0.7:
                message = "Strong match - Faces match with high confidence"
            elif confidence >= 0.5:
                message = "Good match - Faces match"
            else:
                message = "Weak match - Faces match but with lower confidence"
        else:
            if distance < 0.7:
                message = "Close but no match - Faces are similar but not the same person"
            else:
                message = "No match - Faces are clearly different"
        
        result = {
            "success": True,
            "verified": verified,
            "confidence": round(confidence, 4),
            "distance": round(distance, 4),
            "threshold": VERIFICATION_THRESHOLD,
            "message": message
        }
        
        logger.info(f"Verification complete: verified={verified}, confidence={confidence:.4f}, distance={distance:.4f}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during verification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "internal_error",
                "message": f"An error occurred during verification: {str(e)}"
            }
        )


@app.post("/detect-face")
async def detect_face(
    image: UploadFile = File(..., description="Image to detect face in")
) -> Dict:
    """
    Detect if a face exists in the image (utility endpoint)
    
    Useful for pre-validation before submitting to /verify-face
    
    **Returns:**
    - `face_detected`: Whether a face was found
    - `face_count`: Number of faces detected
    - `message`: Result message
    """
    logger.info(f"Face detection request for: {image.filename}")
    
    try:
        # Validate image
        image_bytes = validate_image(image)
        
        # Load and detect faces
        img = face_recognition.load_image_file(io.BytesIO(image_bytes))
        face_locations = face_recognition.face_locations(img)
        face_count = len(face_locations)
        
        result = {
            "success": True,
            "face_detected": face_count > 0,
            "face_count": face_count,
            "message": f"Detected {face_count} face(s) in image"
        }
        
        if face_count == 0:
            result["message"] = "No face detected. Please use a clearer photo."
        elif face_count > 1:
            result["message"] = f"Multiple faces detected ({face_count}). Please use image with single face."
        else:
            result["message"] = "Face detected successfully"
        
        logger.info(f"Face detection complete: {face_count} face(s) found")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Face detection error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Face detection failed: {str(e)}"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
