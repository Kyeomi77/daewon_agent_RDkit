# RDKit SMILES 변환 서비스 + Gemini Enterprise 연동 - 20261020 new

```
rdkit-cloudrun-service/
├── Dockerfile            # Cloud Run 컨테이너
├── .dockerignore / .gcloudignore
├── requirements.txt
├── main.py               # FastAPI + RDKit + GCS
├── openapi.yaml          # API 명세 (문서화 / OpenAPI 도구용)
├── rdkit_agent/          # Gemini Enterprise에 등록할 ADK 에이전트
│   ├── __init__.py
│   ├── agent.py
│   ├── requirements.txt
│   └── .env.example
├── deploy_agent.py       # Agent Engine 배포
└── register_agent.sh     # Gemini Enterprise 등록 (REST)


호출 흐름: Gemini Enterprise 웹앱 → ADK 에이전트(Vertex AI Agent Engine) → Function Calling(`convert_smiles`) → Cloud Run(ID 토큰 인증) → RDKit 변환 → GCS 저장

## 0. 변수

```bash
export PROJECT_ID="uk-adc-core-geminienterprise"
export REGION="asia-northeast3"
export SERVICE_NAME="rdkit-service"
export BUCKET_NAME="${PROJECT_ID}-rdkit-storage"
export RUN_SA="rdkit-run-sa@${PROJECT_ID}.iam.gserviceaccount.com"
export AGENT_LOCATION="us-central1"
export STAGING_BUCKET="gs://${PROJECT_ID}-agent-staging"
export PROJECT_NUMBER="925869106357"

gcloud config set project "$PROJECT_ID"
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
```

## 1. API 활성화

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com storage.googleapis.com \
  aiplatform.googleapis.com discoveryengine.googleapis.com
```

## 2. GCS 버킷 및 Cloud Run 서비스 계정

```bash
gcloud storage buckets create "gs://${BUCKET_NAME}" --location="$REGION" --uniform-bucket-level-access

gcloud iam service-accounts create rdkit-run-sa --display-name="RDKit Cloud Run SA"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${RUN_SA}" --role="roles/storage.objectCreator"
```

## 3. Cloud Run 배포 (인증 필수)

```bash
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --no-allow-unauthenticated \
  --service-account "$RUN_SA" \
  --memory 1Gi --cpu 1 --concurrency 20 --timeout 60 \
  --set-env-vars "GCS_BUCKET_NAME=${BUCKET_NAME}"

export RDKIT_SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')
echo "$RDKIT_SERVICE_URL"
```

테스트:

```bash
TOKEN=$(gcloud auth print-identity-token)
curl -s -H "Authorization: Bearer $TOKEN" "$RDKIT_SERVICE_URL/health"
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"smiles":"CC(=O)OC1=CC=CC=C1C(=O)O"}' "$RDKIT_SERVICE_URL/convert"
# 기대 InChIKey (아스피린): BSYNRYMUTXBXSQ-UHFFFAOYSA-N
gcloud storage ls "gs://${BUCKET_NAME}/conversions/**"
```

## 4. ADK 에이전트 로컬 테스트
```bash
# 가상환경 및 의존성
python3 -m venv .venv && source .venv/bin/activate
pip install -r rdkit_agent/requirements.txt
#   note: This error originates from a subprocess, and is likely not a problem #.  with pip.
#ERROR: Failed building wheel for cryptography
#Failed to build cryptography
#error: failed-wheel-build-for-install 
# pip install --only-binary=:all: cryptography

# 배포 시 사용할 인증 (로컬 ADC)
gcloud auth application-default login
gcloud auth application-default set-quota-project "$PROJECT_ID"

# 배포 (실제 서비스 URL을 그대로 전달)
export RDKIT_SERVICE_URL="https://rdkit-service-wlzvi34knq-du.a.run.app"
python3 deploy_agent.py
export REASONING_ENGINE="projects/925869106357/locations/us-central1/reasoningEngines/1102594933258190848"
#Deployed: projects/925869106357/locations/us-central1/reasoningEngines/1102594933258190848
#gcloud auth application-default login
#adk web      # 브라우저에서 rdkit_agent 선택 후 "아스피린 SMILES를 InChIKey로 바꿔줘"
```
## 5. Agent Engine 배포 및 Cloud Run 호출 권한
# PROJECT_NUMBER 설정
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
# Agent Engine 서비스 에이전트에 Cloud Run 호출 권한 부여
gcloud run services add-iam-policy-binding "$SERVICE_NAME" --region "$REGION" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```
## 6. 배포된 에이전트를 직접 테스트 (Gemini Enterprise 등록 전)
python3 - << 'EOF'
import os
import vertexai
from vertexai import agent_engines

vertexai.init(project=os.environ["PROJECT_ID"], location=os.environ["AGENT_LOCATION"])
# 1) 배포된 에이전트 목록 조회
agents = list(agent_engines.list())
print(f"=== {os.environ['AGENT_LOCATION']} 에 배포된 에이전트: {len(agents)}개 ===")
for a in agents:
    print(" -", a.display_name, "→", a.resource_name)

if not agents:
    raise SystemExit("배포된 에이전트가 없습니다. deploy_agent.py 를 먼저 실행하세요.")

# 2) RDKit 에이전트 자동 선택 (없으면 가장 최근 것)
target = next((a for a in agents if "RDKit" in (a.display_name or "")), agents[0])
print("\n>>> 테스트 대상:", target.resource_name)
print(f'>>> 다음 단계용: export REASONING_ENGINE="{target.resource_name}"\n')

# 3) 테스트 질의
msg = "아스피린 SMILES CC(=O)OC1=CC=CC=C1C(=O)O 를 InChIKey로 변환해줘"
for ev in target.stream_query(user_id="test", message=msg):
    for part in ev.get("content", {}).get("parts", []):
        if "function_call" in part:
            print("[도구 호출]", part["function_call"])
        elif "function_response" in part:
            print("[도구 결과]", part["function_response"])
        elif "text" in part:
            print("[답변]", part["text"])
EOF
```
## 7. Gemini Enterprise 등록
콘솔: Google Cloud 콘솔 → Gemini Enterprise → 대상 앱 → 에이전트 → 에이전트 추가 → "Custom agent via Agent Engine" → 이름/설명 입력, Reasoning Engine 경로에 `$REASONING_ENGINE` 입력 → 저장. 사용자 OAuth 위임이 필요 없으므로 승인(Authorization) 단계는 건너뛴다.

# Gemini Enterprise에 앱이 있는지 여부 확인
curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines?pageSize=200" \
| python3 -c "
import sys, json
for e in json.load(sys.stdin).get('engines', []):
    i = e['name'].split('/')[-1]; n = e.get('displayName','')
    if 'daewon' in (i+n).lower(): print('APP_ID =', i, '| 이름 =', n)"


```bash 
./register_agent.sh
```

등록 후 에이전트 상태를 Enabled로 바꾸면 Gemini Enterprise 웹앱의 에이전트 갤러리에 표시된다.

## 8. 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| 도구 결과 403 | 5단계의 `run.invoker` 바인딩 누락, 또는 ID 토큰 audience가 서비스 URL과 불일치 |
| 도구 결과 400 | 잘못된 SMILES (예: 산소 `O` 대신 숫자 `0`) |
| GCS에 파일 없음 | Cloud Run SA의 `storage.objectCreator` 권한 / `GCS_BUCKET_NAME` 확인. 로그: `gcloud run services logs read $SERVICE_NAME --region $REGION` |
| Gemini Enterprise에서 에이전트 호출 실패 | Discovery Engine 서비스 에이전트(`service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com`)에 Vertex AI 사용자 역할 필요 여부 확인 |
| 에이전트가 InChIKey를 지어냄 | `agent.py` instruction의 "도구 결과만 사용" 지시 유지, 모델 변경 시 재검증 |
