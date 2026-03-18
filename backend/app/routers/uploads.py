import os
import tempfile
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Upload, Transaction, ClassificationRule, User
from ..schemas import UploadResponse
from ..services.file_parser import FileParser
from ..services.classifier import Classifier
from ..services.metrics_calculator import calculate_monthly_metrics
from ..auth.dependencies import get_current_user, get_active_business_id

logger = logging.getLogger(__name__)
router = APIRouter()
parser = FileParser()
classifier = Classifier()

ALLOWED_EXTENSIONS = {".pdf", ".xls", ".xlsx", ".csv"}


def _process_upload(
    upload_id: int,
    file_path: str,
    file_type: str,
    db_url: str,
    business_account_id: Optional[int] = None,
):
    """Background task — cannot use request.state, so BA id is passed explicitly."""
    from sqlalchemy import create_engine, or_
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            return

        upload.status = "processing"
        db.commit()

        # Parse file
        transactions_data = parser.parse(file_path, file_type)

        if not transactions_data:
            upload.status = "failed"
            upload.error_message = "No transactions found in the file"
            db.commit()
            return

        # Load rules: user rules for this BA + all system rules
        rules_q = db.query(ClassificationRule)
        if business_account_id is not None:
            rules_q = rules_q.filter(
                or_(
                    ClassificationRule.business_account_id == business_account_id,
                    ClassificationRule.scope == "system",
                )
            )
        rules = [
            {
                "id":                getattr(r, "id", None),
                "key_phrase":        r.key_phrase,
                "head":              r.head,
                "type":              r.type,
                "rule_type":         getattr(r, "rule_type", "user_learned") or "user_learned",
                "pattern":           getattr(r, "pattern", None),
                "normalized_vendor": getattr(r, "normalized_vendor", None),
                "is_enabled":        getattr(r, "is_enabled", True),
                "confidence":        getattr(r, "confidence", 0.99) or 0.99,
                "scope":             getattr(r, "scope", "user") or "user",
            }
            for r in rules_q.all()
        ]
        classified = classifier.classify_all(transactions_data, rules=rules)

        # Store transactions
        months_affected = set()
        for txn_data in classified:
            txn = Transaction(
                upload_id=upload_id,
                business_account_id=business_account_id,
                date=txn_data["date"],
                description=txn_data["description"],
                amount=txn_data["amount"],
                type=txn_data["type"],
                head=txn_data.get("head"),
                month=txn_data.get("month"),
                comments=txn_data.get("comments"),
                status=txn_data.get("status", "unmapped"),
                classification_confidence=txn_data.get("classification_confidence"),
                raw_debit=txn_data.get("raw_debit"),
                raw_credit=txn_data.get("raw_credit"),
                raw_balance=txn_data.get("raw_balance"),
                matched_rule_id=txn_data.get("matched_rule_id"),
                matched_rule_source=txn_data.get("matched_rule_source"),
            )
            db.add(txn)
            if txn_data.get("month"):
                months_affected.add(txn_data["month"])

        db.commit()

        # Calculate metrics for each month
        for month in months_affected:
            calculate_monthly_metrics(db, month, business_account_id)

        mapped = sum(1 for t in classified if t.get("status") == "mapped")
        unmapped = len(classified) - mapped

        upload.status = "completed"
        upload.row_count = len(classified)
        upload.mapped_count = mapped
        upload.unmapped_count = unmapped
        db.commit()

    except Exception as e:
        logger.error(f"Upload processing error: {e}", exc_info=True)
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if upload:
            upload.status = "failed"
            upload.error_message = str(e)
            db.commit()
    finally:
        db.close()
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    upload = Upload(
        business_account_id=business_id,
        filename=os.path.basename(tmp_path),
        original_filename=file.filename or "unknown",
        file_type=ext.lstrip("."),
        status="pending",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    from ..config import settings
    background_tasks.add_task(
        _process_upload,
        upload.id,
        tmp_path,
        ext.lstrip("."),
        settings.database_url,
        business_id,
    )
    return upload


@router.get("", response_model=List[UploadResponse])
def list_uploads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    return (
        db.query(Upload)
        .filter(Upload.business_account_id == business_id)
        .order_by(Upload.created_at.desc())
        .all()
    )


@router.get("/{upload_id}", response_model=UploadResponse)
def get_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    upload = db.query(Upload).filter(
        Upload.id == upload_id,
        Upload.business_account_id == business_id,
    ).first()
    if not upload:
        raise HTTPException(404, "Upload not found")
    return upload


@router.delete("/{upload_id}")
def delete_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    upload = db.query(Upload).filter(
        Upload.id == upload_id,
        Upload.business_account_id == business_id,
    ).first()
    if not upload:
        raise HTTPException(404, "Upload not found")
    db.delete(upload)
    db.commit()
    return {"message": "Upload deleted"}
