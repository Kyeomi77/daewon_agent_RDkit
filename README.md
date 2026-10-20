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
python3 -m venv //Users/jameskim/Downloads/TKCO/daewon_agent_RDKit/.venv && source /Users/jameskim/Downloads/TKCO/daewon_agent_RDKit/.venv/bin/activate
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
export REASONING_ENGINE="projects/925869106357/locations/us-central1/reasoningEngines/6718548484217110528"
#Deployed: projects/925869106357/locations/us-central1/reasoningEngines/6718548484217110528
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
python3 - << EOF
import vertexai
from vertexai import agent_engines
vertexai.init(project="$PROJECT_ID", location="$AGENT_LOCATION")
app = agent_engines.get("$REASONING_ENGINE")
for ev in app.stream_query(user_id="test", message="아스피린 SMILES CC(=O)OC1=CC=CC=C1C(=O)O 를 InChIKey로 변환해줘"):
    print(ev)
EOF
```
## 7. Gemini Enterprise 등록
콘솔: Google Cloud 콘솔 → Gemini Enterprise → 대상 앱 → 에이전트 → 에이전트 추가 → "Custom agent via Agent Engine" → 이름/설명 입력, Reasoning Engine 경로에 `$REASONING_ENGINE` 입력 → 저장. 사용자 OAuth 위임이 필요 없으므로 승인(Authorization) 단계는 건너뛴다.

REST:

```bash 
APP_ID=daewonpharm-rd-ge_2026101900001 GE_LOCATION=global ./register_agent.sh
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
