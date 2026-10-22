#!/usr/bin/env bash 
# Agent Engine에 배포한 ADK 에이전트를 Gemini Enterprise 앱에 등록 (REST API 방식)
# 콘솔에서 등록할 경우 이 스크립트는 필요 없음.
set -euo pipefail

PROJECT_ID="uk-adc-core-geminienterprise"
APP_ID="daewonpharm-rd-ge_1787731379225"           # 콘솔 > Gemini Enterprise > 앱 목록의 ID
GE_LOCATION="global"                               # 앱 생성 위치: global / us / eu
REASONING_ENGINE="projects/925869106357/locations/us-central1/reasoningEngines/1102594933258190848"

if [[ "$GE_LOCATION" == "global" ]]; then
  ENDPOINT="https://discoveryengine.googleapis.com"
else
  ENDPOINT="https://${GE_LOCATION}-discoveryengine.googleapis.com"
fi

curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${ENDPOINT}/v1alpha/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents" \
  -d @- << JSON
{
  "displayName": "RDKit SMILES 변환기",
  "description": "SMILES 분자 구조를 InChI와 InChIKey로 변환합니다.",
  "adk_agent_definition": {
    "tool_settings": {
      "tool_description": "SMILES 문자열을 InChI, InChIKey, canonical SMILES로 변환할 때 사용"
    },
    "provisioned_reasoning_engine": {
      "reasoning_engine": "${REASONING_ENGINE}"
    }
  }
}
JSON
echo
