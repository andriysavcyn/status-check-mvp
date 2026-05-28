from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from . import models, schemas, database

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Status Check MVP API")

@app.post("/commitments/", response_model=schemas.CommitmentOut)
def create_commitment(commitment: schemas.CommitmentCreate, db: Session = Depends(database.get_db)):
    commitment_data = commitment.model_dump(by_alias=False)
    db_commitment = models.Commitment(**commitment_data)

    db.add(db_commitment)
    db.commit()
    db.refresh(db_commitment)

    return db_commitment

@app.get("/commitments/", response_model=List[schemas.CommitmentOut])
def read_commitments(skip: int=0, limit: int=100, db: Session = Depends(database.get_db)):
    commitments = db.query(models.Commitment).offset(skip).limit(limit).all()
    return commitments

@app.put("/commitments/{commitment_id}", response_model=schemas.CommitmentOut)
def update_commitment(commitment_id: int, commitment: schemas.CommitmentCreate, db: Session = Depends(database.get_db)):
    # Шукаємо запис у базі
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