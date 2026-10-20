"""ADK 에이전트를 Vertex AI Agent Engine에 배포한다. - 20261020 new

사용: python deploy_agent.py
출력되는 resource name(projects/.../reasoningEngines/ID)을 Gemini Enterprise 등록에 사용.
"""
import os

import vertexai
from vertexai import agent_engines

from rdkit_agent.agent import root_agent

PROJECT_ID = os.environ.get("PROJECT_ID", "uk-adc-core-geminienterprise")
AGENT_LOCATION = os.environ.get("AGENT_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", f"gs://{PROJECT_ID}-agent-staging")
RDKIT_SERVICE_URL = os.environ["RDKIT_SERVICE_URL"]  # 반드시 지정

vertexai.init(project=PROJECT_ID, location=AGENT_LOCATION, staging_bucket=STAGING_BUCKET)

app = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)

remote_app = agent_engines.create(
    agent_engine=app,
    display_name="RDKit SMILES Converter",
    description="SMILES를 InChI/InChIKey로 변환하는 RDKit 에이전트",
    requirements=[
        "google-cloud-aiplatform[agent_engines,adk]>=1.95.0",
        "google-adk>=1.0.0",
        "requests>=2.31.0",
        "google-auth>=2.29.0",
    ],
    extra_packages=["./rdkit_agent"],
    env_vars={"RDKIT_SERVICE_URL": RDKIT_SERVICE_URL},
)

print("Deployed:", remote_app.resource_name)
