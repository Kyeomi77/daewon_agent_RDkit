import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from rdkit import Chem
from rdkit.Chem import inchi
from google.cloud import storage

app = FastAPI(
    title="RDKit Molecule Conversion API",
    description="SMILES 입력을 InChI 및 InChIKey로 변환하는 API",
    version="1.0.0"
)

# GCS 버킷 환경 변수 (필요 시 설정)
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
storage_client = storage.Client() if GCS_BUCKET_NAME else None

class ConversionRequest(BaseModel):
    smiles: str = Field(..., description="변환할 유효한 SMILES 문자열", json_schema_extra={"examples": ["CC(=0)OC1=CC=CC=C1C(=0)0"]})

class ConversionResponse(BaseModel):
    smiles: str
    inchi: str
    inchikey: str

def save_to_gcs(data: dict):
    """결과 데이터를 Cloud Storage에 비동기/로그 형태로 저장 (옵션)"""
    if not storage_client or not GCS_BUCKET_NAME:
        return
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        blob = bucket.blob(f"conversions/{timestamp}.json")
        blob.upload_from_string(
            data=json.dumps(data, ensure_ascii=False),
            content_type="application/json"
        )
    except Exception as e:
        # GCS 로깅 실패가 API 응답 실패로 이어지지 않도록 예외 처리
        print(f"GCS Upload Failed: {e}")

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy"}

@app.post("/convert", response_model=ConversionResponse, status_code=status.HTTP_200_OK)
def convert_smiles(request: ConversionRequest):
    smiles_input = request.smiles.strip()
    
    # 1. SMILES 파싱
    mol = Chem.MolFromSmiles(smiles_input)
    if mol is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 SMILES 구조입니다: {smiles_input}"
        )

    # 2. InChI 및 InChIKey 변환
    try:
        mol_inchi = inchi.MolToInchi(mol)
        mol_inchikey = inchi.InchiToInchiKey(mol_inchi)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"변환 중 오류가 발생했습니다: {str(exc)}"
        )

    result = {
        "smiles": smiles_input,
        "inchi": mol_inchi,
        "inchikey": mol_inchikey
    }

    # 3. GCS 저장
    save_to_gcs(result)

    return result
