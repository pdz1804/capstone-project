"""Bedrock AgentCore runtime entrypoint template for BK-MInD.

Environment preparation checklist before deploying this runtime:
- Install dependency: pip install bedrock-agentcore strands-agents
- Set AWS credentials and region (AWS_REGION / AWS_DEFAULT_REGION)
- Align runtime mode in FastAPI backend:
  CHAT_AGENT_RUNTIME=agentcore-runtime
  AGENTCORE_RUNTIME_ARN=<deployed agent runtime ARN>
- Keep DynamoDB chat session/message tables enabled in backend for durable history.

This file is intentionally separate from FastAPI routes so you can deploy the
agent runtime independently and switch execution mode through environment config.
"""

from __future__ import annotations

import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent(
    model=(
        os.getenv("CHAT_AGENT_MODEL")
        or os.getenv("GENERATION_MODEL")
        or os.getenv("BEDROCK_MODEL_ID")
        or None
    )
)


@app.entrypoint
def invoke(payload):
    """Process user input and return a runtime payload for the API adapter."""
    user_message = payload.get("prompt", "Hello")
    result = agent(user_message)
    return {
        "result": str(getattr(result, "message", result)),
        "follow_up_questions": [],
    }


if __name__ == "__main__":
    app.run()
