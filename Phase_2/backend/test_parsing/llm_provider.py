import os
from openai_provider import OpenAIProvider
from bedrock_provider import BedrockProvider

class LLMProvider:
    _instances: dict[str, object] = {}
    @staticmethod
    def create(provider: str = None):
        provider = (provider or os.getenv("PREFER_PROVIDER", "openai")).lower()
        if provider in LLMProvider._instances:
            return LLMProvider._instances[provider]
        if provider == "openai":
            client = OpenAIProvider(
                api_key=os.getenv("OPENAI_API_KEY"),
                default_model=os.getenv("OPENAI_LLM_MODEL", "gpt-5.1"),
            )
        elif provider == "aws_bedrock":
            client = BedrockProvider(
                access_key=os.getenv("AWS_LLM_ACCESS_KEY_ID"),
                secret_key=os.getenv("AWS_LLM_SECRET_ACCESS_KEY"),
                region=os.getenv("AWS_LLM_REGION", "us-west-2"),
                default_model=os.getenv("AWS_LLM_MODEL", "mistral.mistral-large-2407-v1:0"),
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        LLMProvider._instances[provider] = client
        return client
