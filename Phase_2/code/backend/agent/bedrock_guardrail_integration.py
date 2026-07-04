"""Simple AWS Bedrock Guardrail support for converse() calls."""

import os
from typing import Dict, Any, Optional

# Guardrail Configuration (simple boolean mode)
GUARDRAIL_ENABLED = os.getenv("GUARDRAIL_ENABLED", "true").lower() in ("true", "1", "yes")
GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", "42ay3u3pr8vr")
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "DRAFT")


def get_guardrail_config() -> Optional[Dict[str, Any]]:
    """Get guardrail config for Bedrock converse() if enabled.
    
    Returns:
        Dictionary with guardRailConfig for converse() or None if disabled.
    """
    if not GUARDRAIL_ENABLED or not GUARDRAIL_ID:
        return None
    
    return {
        "guardrailIdentifier": GUARDRAIL_ID,
        "guardrailVersion": GUARDRAIL_VERSION,
    }


def add_guardrail_to_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Add guardrail config to Bedrock converse() request if enabled.
    
    Args:
        request: Bedrock converse() request dict
        
    Returns:
        Updated request with guardrail config
    """
    guardrail_config = get_guardrail_config()
    if guardrail_config:
        request["guardrailConfig"] = guardrail_config
    return request
