rdkit-cloudrun-service/
├── Dockerfile
├── requirements.txt
├── main.py
└── openapi.yaml


[Cloud Run 및 Cloud Storage 배포 가이드]
# 1. 환경 변수 설정
PROJECT_ID="uk-adc-core-geminienterprise"
REGION="asia-northeast3" # 서울 리전
SERVICE_NAME="rdkit-service"
BUCKET_NAME="uk-adc-core-geminienterprise-rdkit-storage"

# 2. GCS 버킷 생성 (결과 및 로그 저장용)
gcloud storage buckets create gs://uk-adc-core-geminienterprise-rdkit-storage --location=asia-northeast3

# 3. Artifact Registry 빌드 및 Cloud Run 배포
gcloud run deploy rdkit-service \
    --source . \
    --region asia-northeast3 \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars GCS_BUCKET_NAME=uk-adc-core-geminienterprise-rdkit-storage


