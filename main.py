import os
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import create_document
from schemas import AnalysisLog

app = FastAPI(title="Pashu Mitra AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PredictionResponse(BaseModel):
    module: str
    predictions: List[dict]
    meta: dict

@app.get("/")
def read_root():
    return {"message": "Pashu Mitra AI Backend Running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        # Try to import database module
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# ---------- Utility heuristics (mock AI) ----------

def _mock_classifier_labels(filename: str) -> List[dict]:
    name = filename.lower()
    if any(k in name for k in ["cow", "cattle", "bovine"]):
        return [
            {"label": "Cow", "confidence": 0.92},
            {"label": "Buffalo", "confidence": 0.05},
            {"label": "Yak", "confidence": 0.03},
        ]
    if any(k in name for k in ["dog", "canine"]):
        return [
            {"label": "Dog", "confidence": 0.90},
            {"label": "Wolf", "confidence": 0.06},
            {"label": "Fox", "confidence": 0.04},
        ]
    if any(k in name for k in ["cat", "feline"]):
        return [
            {"label": "Cat", "confidence": 0.91},
            {"label": "Lynx", "confidence": 0.05},
            {"label": "Puma", "confidence": 0.04},
        ]
    return [
        {"label": "Unknown Animal", "confidence": 0.60},
        {"label": "Dog", "confidence": 0.22},
        {"label": "Cat", "confidence": 0.18},
    ]


def _mock_snake_assessment(filename: str) -> List[dict]:
    name = filename.lower()
    venom = False
    label = "Non-venomous Snake"
    if any(k in name for k in ["cobra", "viper", "krait"]):
        venom = True
        label = "Venomous Snake"
    preds = [
        {"label": label, "confidence": 0.88 if venom else 0.82},
        {"label": "Rat Snake", "confidence": 0.08},
        {"label": "Other", "confidence": 0.04},
    ]
    # Attach a simple danger meta
    return preds


def _mock_emotion(filename: str) -> List[dict]:
    name = filename.lower()
    if any(k in name for k in ["happy", "smile"]):
        return [
            {"label": "Happy", "confidence": 0.93},
            {"label": "Relaxed", "confidence": 0.05},
            {"label": "Alert", "confidence": 0.02},
        ]
    if any(k in name for k in ["angry", "growl", "hiss"]):
        return [
            {"label": "Agitated", "confidence": 0.88},
            {"label": "Alert", "confidence": 0.08},
            {"label": "Neutral", "confidence": 0.04},
        ]
    return [
        {"label": "Neutral", "confidence": 0.70},
        {"label": "Curious", "confidence": 0.20},
        {"label": "Relaxed", "confidence": 0.10},
    ]

# ---------- Endpoints ----------

@app.post("/api/classify", response_model=PredictionResponse)
async def classify(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    first = files[0]
    predictions = _mock_classifier_labels(first.filename)
    meta = {
        "filename": first.filename,
        "content_type": first.content_type,
        "files_count": len(files),
    }

    payload = {"module": "classifier", "predictions": predictions, "meta": meta}

    # Log to database
    try:
        log = AnalysisLog(
            module="classifier",
            filenames=[f.filename for f in files],
            content_types=[f.content_type for f in files],
            sizes=[len(await f.read()) for f in files],
            result=payload,
        )
        _ = create_document("analysislog", log)
    except Exception:
        pass  # Best effort logging

    return payload


@app.post("/api/snake", response_model=PredictionResponse)
async def snake(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    first = files[0]
    predictions = _mock_snake_assessment(first.filename)
    venomous = predictions[0]["label"] == "Venomous Snake"
    meta = {
        "filename": first.filename,
        "content_type": first.content_type,
        "danger": "Dangerous" if venomous else "Generally Safe",
        "files_count": len(files),
    }

    payload = {"module": "snake", "predictions": predictions, "meta": meta}

    try:
        log = AnalysisLog(
            module="snake",
            filenames=[f.filename for f in files],
            content_types=[f.content_type for f in files],
            sizes=[len(await f.read()) for f in files],
            result=payload,
        )
        _ = create_document("analysislog", log)
    except Exception:
        pass

    return payload


@app.post("/api/emotion", response_model=PredictionResponse)
async def emotion(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    first = files[0]
    predictions = _mock_emotion(first.filename)
    meta = {
        "filename": first.filename,
        "content_type": first.content_type,
        "files_count": len(files),
    }

    payload = {"module": "emotion", "predictions": predictions, "meta": meta}

    try:
        log = AnalysisLog(
            module="emotion",
            filenames=[f.filename for f in files],
            content_types=[f.content_type for f in files],
            sizes=[len(await f.read()) for f in files],
            result=payload,
        )
        _ = create_document("analysislog", log)
    except Exception:
        pass

    return payload


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
