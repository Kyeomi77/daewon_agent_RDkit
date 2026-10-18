"""main.py 로컬 테스트 (pytest + FastAPI TestClient)

실행: pytest -v
GCS_BUCKET_NAME 환경변수가 없으면 GCS 업로드는 자동으로 건너뜁니다.
"""
import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

ASPIRIN_SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"
ASPIRIN_INCHIKEY = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["inchi_available"] is True


def test_convert_aspirin():
    res = client.post("/convert", json={"smiles": ASPIRIN_SMILES})
    assert res.status_code == 200
    body = res.json()
    assert body["smiles"] == ASPIRIN_SMILES
    assert body["canonical_smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert body["inchi"].startswith("InChI=1S/C9H8O4/")
    assert body["inchikey"] == ASPIRIN_INCHIKEY


def test_convert_strips_whitespace():
    res = client.post("/convert", json={"smiles": f"  {ASPIRIN_SMILES}  "})
    assert res.status_code == 200
    assert res.json()["smiles"] == ASPIRIN_SMILES


@pytest.mark.parametrize("smiles", ["C1CC", "XYZ", "C(C"])
def test_convert_invalid_smiles(smiles):
    res = client.post("/convert", json={"smiles": smiles})
    assert res.status_code == 400
    assert "유효하지 않은 SMILES" in res.json()["detail"]


def test_convert_whitespace_only():
    res = client.post("/convert", json={"smiles": "   "})
    assert res.status_code == 400


def test_convert_empty_string_validation():
    # min_length=1 위반 → Pydantic 검증 오류
    res = client.post("/convert", json={"smiles": ""})
    assert res.status_code == 422


def test_convert_missing_field():
    res = client.post("/convert", json={})
    assert res.status_code == 422


def test_background_gcs_task_called(monkeypatch):
    """GCS 업로드 함수가 변환 결과와 함께 백그라운드로 호출되는지 확인 (실제 업로드 없음)"""
    calls = []
    monkeypatch.setattr(main, "save_to_gcs", lambda data: calls.append(data))

    res = client.post("/convert", json={"smiles": "CCO"})
    assert res.status_code == 200
    assert len(calls) == 1
    assert calls[0]["inchikey"] == res.json()["inchikey"]


def test_save_to_gcs_skips_without_bucket(monkeypatch):
    """버킷 미설정 시 클라이언트를 만들지 않고 조용히 종료"""
    monkeypatch.setattr(main, "GCS_BUCKET_NAME", None)
    monkeypatch.setattr(main, "_storage_client", None)
    main.save_to_gcs({"smiles": "CCO"})  # 예외 없이 끝나야 함
    assert main._storage_client is None
