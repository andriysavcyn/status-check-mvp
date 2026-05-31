import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app import models, schemas, database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Status Check MVP API")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=FileResponse)
def read_root():
    return os.path.join(STATIC_DIR, "index.html")


@app.post("/commitments/", response_model=schemas.CommitmentOut)
def create_commitment(commitment: schemas.CommitmentCreate, db: Session = Depends(database.get_db)):
    commitment_data = commitment.model_dump(by_alias=False)
    db_commitment = models.Commitment(**commitment_data)
    
    db.add(db_commitment)
    db.commit()
    db.refresh(db_commitment)
    return db_commitment

@app.get("/commitments/", response_model=List[schemas.CommitmentOut])
def read_commitments(
    skip: int = 0, 
    limit: int = 100, 
    project: Optional[str] = None,      
    checker_id: Optional[int] = None,   
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Commitment)

    if project:
        query = query.filter(models.Commitment.project.ilike(f"%{project}%"))

    if checker_id:
        query = query.filter(models.Commitment.checker_id == checker_id)

    commitments = query.offset(skip).limit(limit).all()
    return commitments

@app.put("/commitments/{commitment_id}", response_model=schemas.CommitmentOut)
def update_commitment(commitment_id: int, commitment: schemas.CommitmentCreate, db: Session = Depends(database.get_db)):
    db_commitment = db.query(models.Commitment).filter(models.Commitment.id == commitment_id).first()
    if db_commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    
    update_data = commitment.model_dump(by_alias=False)
    for key, value in update_data.items():
        setattr(db_commitment, key, value)
        
    db.commit()
    db.refresh(db_commitment)
    return db_commitment

@app.delete("/commitments/{commitment_id}")
def delete_commitment(commitment_id: int, db: Session = Depends(database.get_db)):
    db_commitment = db.query(models.Commitment).filter(models.Commitment.id == commitment_id).first()
    if db_commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    
    db.delete(db_commitment)
    db.commit()
    return {"detail": "Commitment deleted successfully"}