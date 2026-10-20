# - 20261020 new
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from rdkit import Chem, RDLogger
from rdkit.Chem import inchi

# RDKit 파싱 경고가 stderr로 쏟아지지 않도록 억제 (오류는 API 응답으로 처리)
RDLogger.DisableLog("rdApp.*")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rdkit-service")

app = FastAPI(
    title="RDKit Conversion API",
    description="SMILES 입력을 InChI 및 InChIKey로 변환하는 API",
    version="1.0.1",
)

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
_storage_client = None


def get_storage_client():
    """GCS 클라이언트를 최초 사용 시점에 생성 (콜드 스타트 단축, 로컬 실행 시 인증 오류 방지)"""
    global _storage_client
    if _storage_client is None and GCS_BUCKET_NAME:
        from google.cloud import storage
        _storage_client = storage.Client()
    return _storage_client


class ConversionRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="변환할 유효한 SMILES 문자열",
        # 수정: 숫자 0 → 원소 기호 O (원본 예시는 파싱 불가)
        json_schema_extra={"examples": ["CC(=O)OC1=CC=CC=C1C(=O)O"]},
    )


class ConversionResponse(BaseModel):
    smiles: str
    canonical_smiles: str
    inchi: str
    inchikey: str


def save_to_gcs(data: dict) -> None:
    """결과를 GCS에 저장. 응답 반환 후 BackgroundTasks로 실행되며 실패해도 API 응답에 영향 없음."""
    client = get_storage_client()
    if client is None:
        return
    try:
        now = datetime.now(timezone.utc)  # utcnow()는 Python 3.12부터 deprecated
        blob_name = f"conversions/{now:%Y/%m/%d}/{now:%H%M%S_%f}_{uuid.uuid4().hex[:8]}.json"
        payload = {**data, "created_at": now.isoformat()}
        client.bucket(GCS_BUCKET_NAME).blob(blob_name).upload_from_string(
            data=json.dumps(payload, ensure_ascii=False),
            content_type="application/json",
        )
    except Exception:
        logger.exception("GCS upload failed")


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy", "inchi_available": inchi.INCHI_AVAILABLE}


@app.post("/convert", response_model=ConversionResponse, status_code=status.HTTP_200_OK)
def convert_smiles(request: ConversionRequest, background_tasks: BackgroundTasks):
    smiles_input = request.smiles.strip()
    if not smiles_input:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "SMILES 문자열이 비어 있습니다.")

    # 1. SMILES 파싱
    mol: Optional[Chem.Mol] = Chem.MolFromSmiles(smiles_input)
    if mol is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 SMILES 구조입니다: {smiles_input}",
        )

    # 2. InChI / InChIKey 변환
    if not inchi.INCHI_AVAILABLE:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "RDKit 빌드에 InChI 지원이 없습니다.")
    try:
        mol_inchi = inchi.MolToInchi(mol)
        # MolToInchi는 실패 시 예외 대신 빈 문자열을 반환할 수 있음
        if not mol_inchi:
            raise ValueError("InChI 생성 결과가 비어 있습니다.")
        mol_inchikey = inchi.InchiToInchiKey(mol_inchi)
        if not mol_inchikey:
            raise ValueError("InChIKey 생성 결과가 비어 있습니다.")
    except Exception as exc:
        logger.exception("Conversion failed for %s", smiles_input)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"변환 중 오류가 발생했습니다: {exc}",
        )

    result = {
        "smiles": smiles_input,
        "canonical_smiles": Chem.MolToSmiles(mol),
        "inchi": mol_inchi,
        "inchikey": mol_inchikey,
    }

    # 3. GCS 저장 (응답 지연 없이 백그라운드 실행)
    background_tasks.add_task(save_to_gcs, result)
    return result
