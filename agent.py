"""Gemini Enterprise에 등록할 ADK 에이전트. - 20261020 new

Cloud Run RDKit 서비스를 Function Calling 도구로 호출한다.
Agent Engine에서 실행될 때는 메타데이터 서버를 통해 ID 토큰을 자동 발급받는다.
"""
import os

import google.auth.transport.requests
import google.oauth2.id_token
import requests
from google.adk.agents import Agent

RDKIT_SERVICE_URL = os.environ.get(
    "RDKIT_SERVICE_URL",
    "https://rdkit-service-925869106357.asia-northeast3.run.app",
).rstrip("/")
TIMEOUT_SEC = 30


def _auth_headers() -> dict:
    """Cloud Run 호출용 ID 토큰 (audience = 서비스 URL)."""
    auth_req = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(auth_req, RDKIT_SERVICE_URL)
    return {"Authorization": f"Bearer {token}"}


def convert_smiles(smiles: str) -> dict:
    """SMILES 문자열을 표준 InChI, InChIKey, canonical SMILES로 변환한다.

    사용자가 분자 구조(SMILES)를 제시하고 InChI/InChIKey 변환, 구조 식별자 생성,
    동일 화합물 여부 확인을 요청할 때 사용한다.

    Args:
        smiles: 변환할 SMILES 문자열. 예: "CC(=O)OC1=CC=CC=C1C(=O)O" (아스피린)

    Returns:
        성공 시 {"status": "success", "smiles", "canonical_smiles", "inchi", "inchikey"},
        실패 시 {"status": "error", "error_message"}.
    """
    try:
        resp = requests.post(
            f"{RDKIT_SERVICE_URL}/convert",
            json={"smiles": smiles},
            headers=_auth_headers(),
            timeout=TIMEOUT_SEC,
        )
    except Exception as exc:
        return {"status": "error", "error_message": f"RDKit 서비스 호출 실패: {exc}"}

    if resp.status_code == 200:
        return {"status": "success", **resp.json()}
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = resp.text[:500]
    return {"status": "error", "http_status": resp.status_code, "error_message": str(detail)}


root_agent = Agent(
    name="rdkit_agent",
    model=os.environ.get("AGENT_MODEL", "gemini-2.5-flash"),
    description="SMILES 분자 구조를 InChI / InChIKey로 변환하는 화학정보학 에이전트",
    instruction=(
        "너는 화학정보학 어시스턴트다. 사용자가 SMILES를 주거나 InChI/InChIKey 변환을 요청하면 "
        "반드시 convert_smiles 도구를 호출하고, 도구 결과의 값만 그대로 제시한다. "
        "InChI나 InChIKey를 직접 추측하거나 생성하지 않는다. "
        "여러 분자가 주어지면 각각 도구를 호출하고 표로 정리한다. "
        "도구가 error를 반환하면 그 메시지를 사용자에게 알리고 SMILES 확인을 요청한다. "
        "화합물 이름만 주어지면 네가 아는 SMILES를 제시하되, 그 SMILES가 추정임을 밝히고 도구로 변환한다."
    ),
    tools=[convert_smiles],
)
