# bedrock_provider.py
import asyncio
import base64
import json
import uuid
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None
    ClientError = Exception

from .base import BaseLLMProvider
from agent.bedrock_guardrail_integration import get_guardrail_config

_executor = ThreadPoolExecutor(max_workers=10)


class _AttrDict(dict):
    """Dict that also exposes keys as attributes for OpenAI-style access."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


class ToolCallBlock(_AttrDict):
    pass


class OutputTextBlock(_AttrDict):
    pass


class BedrockProvider(BaseLLMProvider):
    """
    Bedrock provider fully adapted to OpenAI Responses API format.
    Handles:
      - dynamic region
      - model restrictions (no system, no access, provisioned only)
      - tool calling
      - OpenAI-style conversation format
    """

    def __init__(self, access_key: str, secret_key: str, region: str, default_model: str):
        if boto3 is None:
            raise ImportError("boto3 is required to use the Bedrock provider. Please install boto3.")
        self.access_key = access_key
        self.secret_key = secret_key
        self.default_region = region
        self.default_model = default_model
        self.client = self._create_client(region)

    # Known model limitations (for auto-fix)
    NO_ACCESS = ["anthropic.claude-3"]
    NO_SYSTEM = ["mistral", "mixtral", "amazon.titan-text"]
    PROVISIONED_ONLY = ["anthropic.claude-3-opus"]

    def _create_client(self, region: str):
        session = boto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=region,
        )
        return session.client("bedrock-runtime")

    def _is_prefix_in(self, model: str, prefixes: List[str]):
        return any(model.startswith(p) for p in prefixes)

    async def create(
        self,
        instructions: Optional[str] = None,
        input: Optional[Any] = None,
        *,
        model: Optional[str] = None,
        region: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:

        selected_model = model or self.default_model

        # Block models you cannot use
        if self._is_prefix_in(selected_model, self.NO_ACCESS):
            raise RuntimeError(f"Model '{selected_model}' is not available for this AWS account.")

        # Region override
        client = self.client if (not region or region == self.default_region) else self._create_client(region)

        # tools_enabled: bật chế độ trả về block khi có tools
        tools_enabled = bool(tools)

        # Simple string input
        if isinstance(input, str):
            return await self._run_single(
                client,
                selected_model,
                instructions,
                input,
                tools,
                tools_enabled,
                **kwargs,
            )

        # Conversation
        if isinstance(input, list):
            return await self._handle_conversation(
                client,
                input,
                selected_model,
                instructions,
                tools,
                tool_choice,
                tools_enabled,
            )

        return await self._run_single(
            client,
            selected_model,
            instructions,
            json.dumps(input),
            tools,
            tools_enabled,
            **kwargs,
        )

    async def _run_single(self, client, model, instructions, text, tools, tools_enabled: bool, **kwargs):
        system_blocks = [{"text": instructions}] if instructions else None
        messages = [{"role": "user", "content": [{"text": text}]}]

        # If model does NOT support system messages → remove system
        if system_blocks and self._is_prefix_in(model, self.NO_SYSTEM):
            system_blocks = None

        req = {
            "modelId": model,
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": kwargs.get("max_tokens", 1024),
                "temperature": float(kwargs.get("temperature", 0.2)),
            }
        }

        if system_blocks:
            req["system"] = system_blocks

        tool_cfg = self._build_tool_config(tools)
        if tool_cfg:
            req["toolConfig"] = tool_cfg

        # Add guardrail config if enabled
        guardrail_cfg = get_guardrail_config()
        if guardrail_cfg:
            req["guardrailConfig"] = guardrail_cfg

        def _call():
            try:
                return client.converse(**req)
            except ClientError as e:
                err = str(e)

                # Provisioned-only model
                if "on-demand throughput isn’t supported" in err:
                    raise RuntimeError(f"Model '{model}' requires Provisioned Throughput.")

                # Model does not support system messages → auto retry
                if "doesn't support system messages" in err:
                    req.pop("system", None)
                    return client.converse(**req)

                raise RuntimeError(f"Bedrock error: {err}")

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(_executor, _call)
        return self._normalize_output(resp, tools_enabled=tools_enabled)

    async def _handle_conversation(
        self,
        client,
        messages,
        model,
        instructions,
        tools,
        tool_choice,
        tools_enabled: bool,
    ):
        bedrock_messages = []
        system_blocks = []

        # If model cannot use system → ignore instructions
        if instructions and not self._is_prefix_in(model, self.NO_SYSTEM):
            system_blocks.append({"text": instructions})

        for msg in messages:
            if msg.get("role") == "system":
                if not self._is_prefix_in(model, self.NO_SYSTEM):
                    system_blocks.append({"text": msg["content"]})
                continue

            if "role" in msg:
                role = msg["role"]
                content = msg.get("content")
                content_blocks = self._build_content_blocks(content)
                bedrock_messages.append({"role": role, "content": content_blocks})
                continue

            # Tool calls (OpenAI style)
            if msg.get("type") == "tool_call":
                bedrock_messages.append({
                    "role": "assistant",
                    "content": [{
                        "toolUse": {
                            "toolUseId": msg.get("tool_call_id"),
                            "name": msg["name"],
                            "input": msg.get("arguments", {})
                        }
                    }]
                })
                continue

            # Tool results
            if msg.get("type") in ("function_call_output", "tool_result"):
                bedrock_messages.append({
                    "role": "user",
                    "content": [{
                        "toolResult": {
                            "toolUseId": msg.get("call_id"),
                            "content": [{"text": json.dumps(msg.get("output"))}]
                        }
                    }]
                })
                continue

        req = {
            "modelId": model,
            "messages": bedrock_messages,
            "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2},
        }

        if system_blocks:
            req["system"] = system_blocks

        tool_cfg = self._build_tool_config(tools, tool_choice)
        if tool_cfg:
            req["toolConfig"] = tool_cfg

        # Add guardrail config if enabled
        guardrail_cfg = get_guardrail_config()
        if guardrail_cfg:
            req["guardrailConfig"] = guardrail_cfg

        def _call():
            try:
                return client.converse(**req)
            except ClientError as e:
                err = str(e)

                if "doesn't support system messages" in err:
                    req.pop("system", None)
                    return client.converse(**req)

                if "invalid sequence as part of ToolUse" in err:
                    req.pop("toolConfig", None)
                    return client.converse(**req)

                if "toolConfig.toolChoice.tool field" in err:
                    tool_cfg = req.get("toolConfig") or {}
                    # downgrade explicit tool choice to auto when unsupported
                    tool_cfg["toolChoice"] = {"auto": {}}
                    req["toolConfig"] = tool_cfg
                    return client.converse(**req)

                raise RuntimeError(err)

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(_executor, _call)
        return self._normalize_output(resp, tools_enabled=tools_enabled)

    def _decode_image(self, image_url):
        if not image_url:
            return None, None

        try:
            url_str = image_url.get("url") if isinstance(image_url, dict) else str(image_url)
            if "," not in url_str:
                return None, None

            header, data = url_str.split(",", 1)
            image_format = header.split(";")[0].split("/")[-1] or "png"
            image_bytes = base64.b64decode(data)
            return image_format, image_bytes
        except Exception:
            return None, None

    def _build_content_blocks(self, content):
        blocks = []
        if isinstance(content, list):
            for item in content:
                item_type = item.get("type")
                if item_type in {"text", "input_text"}:
                    blocks.append({"text": item.get("text", "")})
                elif item_type in {"image_url", "input_image"}:
                    fmt, img_bytes = self._decode_image(item.get("image_url", ""))
                    if img_bytes:
                        blocks.append({"image": {"format": fmt, "source": {"bytes": img_bytes}}})

        if not blocks:
            blocks.append({"text": content if isinstance(content, str) else json.dumps(content)})

        return blocks

    def _build_tool_config(self, tools, tool_choice=None):
        if not tools:
            return None
        specs = []
        for t in tools:
            specs.append({
                "toolSpec": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "inputSchema": {"json": t.get("parameters", {})},
                }
            })
        tool_cfg = {"tools": specs}

        # Respect explicit tool choice when provided
        if tool_choice and tool_choice.get("type") == "function":
            name = tool_choice.get("name")
            if name:
                tool_cfg["toolChoice"] = {"tool": {"name": name}}
                return tool_cfg

        tool_cfg["toolChoice"] = {"auto": {}}
        return tool_cfg

    def _normalize_output(self, resp: Dict[str, Any], tools_enabled: bool):
        """
        Nếu tools_enabled=False → trả string (merged text)
        Nếu tools_enabled=True → trả list block:
          - OutputMessageBlock (type="message")
          - ToolCallBlock (type="function_call")
        """
        message = resp.get("output", {}).get("message", {})
        content = message.get("content", [])
        role = message.get("role", "assistant")

        # Gom text chunk
        text_chunks = [c["text"] for c in content if "text" in c]
        merged_text = "".join(text_chunks)

        # Nếu không dùng tools → behave như output_text
        if not tools_enabled:
            return merged_text

        blocks: List[_AttrDict] = []

        if merged_text:
            blocks.append(
                OutputTextBlock(
                    {
                        "type": "message",
                        "role": role,
                        "content": merged_text,
                    }
                )
            )

        # ToolUse → function_call
        for c in content:
            tu = c.get("toolUse")
            if not tu:
                continue
            name = tu.get("name")
            tool_input = tu.get("input", {})
            call_id = tu.get("toolUseId") or str(uuid.uuid4())

            blocks.append(
                ToolCallBlock(
                    {
                        "type": "function_call",
                        "name": name,
                        "arguments": json.dumps(tool_input),
                        "call_id": call_id,
                        "tool_call_id": call_id,
                    }
                )
            )

        return blocks
