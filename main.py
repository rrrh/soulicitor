import sqlite3
import csv
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

DB_FILE = "vinyl.db"

# --- Pydantic Models for Form Validation ---
class TrackCreate(BaseModel):
    title: str
    bpm: Optional[int] = None
    style: Optional[str] = None
    runtime: Optional[str] = None
    rating: int
    comment: Optional[str] = None

class RecordCreate(BaseModel):
    type: str
    title: Optional[str] = None
    tracks: List[TrackCreate]

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS Records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK(type IN ('7"', '12"')),
        title TEXT,
        CONSTRAINT chk_title_type CHECK (
            (type = '12"' AND title IS NOT NULL AND title != '') OR 
            (type = '7"' AND title IS NULL)
        )
    );
    CREATE TABLE IF NOT EXISTS Tracks (
        track_id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        bpm INTEGER CHECK(bpm > 0),
        style TEXT,
        runtime TEXT,
        rating INTEGER CHECK(rating >= 1 AND rating <= 5),
        comment TEXT,
        FOREIGN KEY (record_id) REFERENCES Records(record_id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---

@app.get("/records")
def get_collection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM Records")
    records = [dict(row) for row in cursor.fetchall()]
    
    for record in records:
        cursor.execute("SELECT * FROM Tracks WHERE record_id = ?", (record["record_id"],))
        record["tracks"] = [dict(row) for row in cursor.fetchall()]
        
    conn.close()
    return records

@app.post("/records")
def add_record(record: RecordCreate):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO Records (type, title) VALUES (?, ?)", (record.type, record.title))
        record_id = cursor.lastrowid
        
        for track in record.tracks:
            cursor.execute("""
                INSERT INTO Tracks (record_id, title, bpm, style, runtime, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (record_id, track.title, track.bpm, track.style, track.runtime, track.rating, track.comment))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    
    return {"message": "Record added successfully"}

@app.get("/export")
def export_csv():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Join records and tracks to flatten the data for CSV
    cursor.execute("""
        SELECT r.type, r.title, t.title, t.bpm, t.style, t.runtime, t.rating, t.comment
        FROM Records r
        JOIN Tracks t ON r.record_id = t.record_id
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Record_Type", "Record_Title", "Track_Title", "BPM", "Style", "Runtime", "Rating", "Comment"])
    writer.writerows(rows)
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=vinyl_collection.csv"}
    )

@app.post("/import")
async def import_csv(file: UploadFile = File(...)):
    content = await file.read()
    decoded = content.decode('utf-8').splitlines()
    reader = csv.DictReader(decoded)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        for row in reader:
            rtype = row.get("Record_Type", '12"')
            rtitle = row.get("Record_Title")
            if rtype == '7"': rtitle = None # Enforce rule for imports
            
            cursor.execute("INSERT INTO Records (type, title) VALUES (?, ?)", (rtype, rtitle))
            record_id = cursor.lastrowid
            
            bpm = int(row.get("BPM")) if row.get("BPM") else None
            rating = int(row.get("Rating")) if row.get("Rating") else 3
            
            cursor.execute("""
                INSERT INTO Tracks (record_id, title, bpm, style, runtime, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (record_id, row.get("Track_Title"), bpm, row.get("Style"), row.get("Runtime"), rating, row.get("Comment")))
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error importing CSV: {str(e)}")
    finally:
        conn.close()
        
    return {"message": "Import successful"}
