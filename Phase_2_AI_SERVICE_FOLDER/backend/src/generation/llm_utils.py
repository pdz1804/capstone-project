"""Lightweight helpers to build prompts and invoke configured LLM clients."""

import json
from typing import Any, Callable, Dict, List, Optional

try:
    import tiktoken
except Exception:  # pragma: no cover - optional dependency
    tiktoken = None


def _supports_openai_responses(llm: Any) -> bool:
    client = getattr(llm, "client", None)
    return bool(
        client
        and hasattr(client, "responses")
        and hasattr(client.responses, "create")
    )


def _serialize_output(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, ensure_ascii=False, default=str)
    except Exception:
        return str(output)


def _get_encoding(model: str):
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


def _count_tokens(text: str, encoding) -> int:
    if not text:
        return 0
    if encoding is None:
        return len(str(text).split())
    return len(encoding.encode(str(text)))


def _estimate_usage(
    messages: List[Dict[str, Any]],
    output: Any,
    model: str,
) -> Dict[str, int]:
    encoding = _get_encoding(model)
    prompt_tokens = 0
    for msg in messages or []:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            prompt_tokens += _count_tokens(str(content), encoding)
        else:
            prompt_tokens += _count_tokens(str(msg), encoding)
    completion_tokens = _count_tokens(_serialize_output(output), encoding)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _build_messages(system_prompt: str, user_prompt: Optional[str]) -> List[Dict[str, str]]:
    """Return chat-style message list from system + optional user prompt.

    Args:
        system_prompt: System message content.
        user_prompt: User message content (optional).
    """

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if user_prompt is not None:
        messages.append({"role": "user", "content": user_prompt})
    return messages


async def call_llm(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    user_prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    tools: Any = None,
    tool_choice: Any = None,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Call the LLM with assembled params, optional tools, and messages.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System message content.
        user_prompt: User message content (ignored if messages provided).
        messages: Pre-built message list (overrides user_prompt).
        temperature: Optional temperature override.
        top_p: Optional top_p override.
        tools: Optional tool definitions.
        tool_choice: Optional tool choice payload.
    """

    payload_messages = messages if messages is not None else _build_messages(system_prompt, user_prompt)

    kwargs: Dict[str, Any] = {
        **llm_params_fn(model),
        "input": payload_messages,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    usage_payload = None
    if token_usage_logger and _supports_openai_responses(llm):
        response = await llm.client.responses.create(**kwargs)
        output = response.output if tools else response.output_text
        usage_payload = getattr(response, "usage", None)
    else:
        output = await llm.create(**kwargs)

    if token_usage_logger and token_context is not None:
        if usage_payload is None:
            usage_payload = _estimate_usage(payload_messages, output, model)
        token_usage_logger(
            usage_payload,
            model,
            model_type or "llm",
            token_context,
        )

    return output


async def summarize_json_text(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    text: str,
    temperature: float | None = 0,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Summarize JSON text with a provided system prompt.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System instructions for summarization.
        text: JSON string to summarize.
        temperature: Optional temperature override.
    """
    user_prompt = f"Here is the json text to summarize:\n{text}"
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def validate_heading_text(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    heading: str,
    tools: Any = None,
    tool_choice: Any = None,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Validate a heading string using a tool-enabled LLM call.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System instructions for heading validation.
        heading: Heading text to validate.
        tools: Tool definitions for validation.
        tool_choice: Tool selection payload.
    """
    user_prompt = "Here is the heading text to validate:\n" + heading
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=tools,
        tool_choice=tool_choice,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def extract_requirements_from_text(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    heading_text: str,
    content: str,
    tools: Any = None,
    tool_choice: Any = None,
    temperature: float = None,
    top_p: float = None,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Extract requirements from plain text content plus heading context.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: Extraction system prompt.
        heading_text: Heading of the content block.
        content: Body text to extract from.
        tools: Tool definitions for extraction.
        tool_choice: Tool selection payload.
    """
    user_prompt = "Here is the document:\n" + content
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        top_p=top_p,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def extract_requirements_with_prompt(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: Any = None,
    tool_choice: Any = None,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Extract requirements using a pre-built user prompt (e.g., table row message).

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: Extraction system prompt.
        user_prompt: Pre-built user prompt to send.
        tools: Tool definitions for extraction.
        tool_choice: Tool selection payload.
    """
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=tools,
        tool_choice=tool_choice,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def bilingual_equivalence_llm(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    req1_context: str,
    req2_context: str,
    temperature: float = None,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Ask LLM to decide if two requirement contexts are bilingual equivalents.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System instructions for bilingual equivalence.
        req1_context: Flattened context for requirement A.
        req2_context: Flattened context for requirement B.
        temperature: Optional temperature override.
    """
    user_prompt = f"""
            Compare the following two requirement entries and decide if they are bilingual equivalents.

            Requirement A:
            {req1_context}

            Requirement B:
            {req2_context}

            Answer only YES or NO.
        """
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def bilingual_difference_language_llm(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    content1: str,
    content2: str,
    temperature: float = None,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Check if two contents are in different languages (YES/NO).

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System prompt for bilingual difference check.
        content1: First content string.
        content2: Second content string.
        temperature: Optional temperature override.
    """
    user_prompt = (
        f"Content A:\n{content1}\n\nContent B:\n{content2}\n\nReturn YES or NO only."
    )
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def decide_keep_modified_llm(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    old_text: str,
    new_text: str,
    temperature: float | None = 0,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Decide to KEEP or SKIP modified content by prompting the LLM.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System instructions for diff filtering.
        old_text: Previous requirement text.
        new_text: New requirement text.
        temperature: Optional temperature override.
    """
    user_prompt = (
        "Old requirement:\n"
        f"{old_text}\n\n"
        "New requirement:\n"
        f"{new_text}\n\n"
        "Should this change be kept (KEEP) or skipped as trivial (SKIP)?"
    )
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def decide_keep_deleted_llm(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    system_prompt: str,
    old_text: str,
    heading_path: str = "",
    temperature: float | None = 0,
    token_context: Optional[dict] = None,
    model_type: Optional[str] = None,
    token_usage_logger: Optional[Callable[[Any, str, str, Optional[dict]], None]] = None,
):
    """Decide to KEEP or SKIP a deleted requirement fragment.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        system_prompt: System instructions for delete filtering.
        old_text: Deleted text to evaluate.
        heading_path: Optional heading context string.
        temperature: Optional temperature override.
    """
    user_prompt = (
        "Deleted requirement text:\n"
        f"{old_text}\n\n"
        "Heading path/context:\n"
        f"{heading_path or '-'}\n\n"
        "Should this deleted content be kept (KEEP) or skipped as meaningless/noise (SKIP)?"
    )
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        token_context=token_context,
        model_type=model_type,
        token_usage_logger=token_usage_logger,
    )


async def detect_sheet_layout_type(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    sheet_data: str,
    sheet_structure: str,
    tools: Any = None,
    tool_choice: Any = None,
):
    """Detect Excel sheet layout type (table vs zone).

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        sheet_data: Complete sheet data as text.
        sheet_structure: Sheet structure metadata (dimensions, borders, etc.).
        tools: Tool definitions for structured output.
        tool_choice: Tool selection payload to force structured output.
        temperature: Optional temperature override.
    """
    system_prompt = """You are an Excel layout analyzer. Your task is to classify Excel sheet layouts into two types:

1. TABLE LAYOUT: Sheet contains one or multiple distinct tables with clear column headers.
   - Key characteristics:
     * Has a header row where EACH COLUMN has its own concise header describing that column's content
     * Headers are typically in row 1 (or first few rows) and apply to all data rows below
     * Data rows follow a consistent structure with one value per column
     * Each column contains consistent data types (all names, all dates, etc.)
     * The number of columns is relatively small and each has a clear purpose

2. ZONE LAYOUT: Sheet is organized into horizontal zones/sections rather than columnar tables.
   - Key characteristics:
     * NO clear header row where each column has its own concise header
     * Instead, has zone labels/section headers spread horizontally (e.g., "model" zone, "event" zone, "Testcase" zone)
     * Content within each zone may span multiple columns without individual column headers
     * Very wide sheets (50+ columns) with zone divisions
     * More like a form or document layout than a data table
     * First column may be mostly empty or have occasional section markers
     * First few rows often have field labels (not column headers) like "model", "specification", "purpose"

CRITICAL DISTINCTION:
- TABLE: Row 1 has "ID | Name | Date | Status" where each header describes ONE column
- ZONE: Row 1 might have "All Items" or empty, rows 2-5 have labels like "model", "specification" spread across columns

Analyze both the data content and structure metadata to determine the layout type."""

    user_prompt = f"""Complete Excel sheet data:

{sheet_data}

Sheet structure metadata:
{sheet_structure}

Based on the complete data and structure, classify this sheet layout as either "table" or "zone".

ANALYSIS CHECKLIST:
1. Check first row: Does it have ONE concise header per column (TABLE) or zone labels/empty/section marker (ZONE)?
2. Check data organization:
   - Does each column have consistent data type throughout (TABLE)?
   - Or is data spread horizontally in zones with multiple columns per section (ZONE)?

Make your decision based on which pattern fits better."""

    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=tools,
        tool_choice=tool_choice,
    )


async def flatten_table_to_hierarchy(
    llm: Any,
    llm_params_fn: Callable[[str], Dict[str, Any]],
    *,
    model: str,
    table_data: str,
    layout_type: str,
    tools: Any = None,
    tool_choice: Any = None,
):
    """Flatten table data into hierarchical structure using LLM.

    Args:
        llm: Client exposing `create` API.
        llm_params_fn: Function that returns provider-specific params per model.
        model: Model name to use.
        table_data: Table data as markdown or text.
        layout_type: Either "table" or "zone".
        tools: Tool definitions for structured output.
        tool_choice: Tool selection payload to force structured output.
        temperature: Optional temperature override.
    """
    if layout_type == "table":
        system_prompt = """You are a table analyzer that converts table markdown into hierarchical entries.

Your task:
1. Analyze the TABLE HEADERS to understand the column/property names
2. Identify which columns form the PRIMARY KEY (first-level identifier) for each entry
3. Group rows by the primary key columns to create hierarchical entries
4. Create nested structure showing the relationships

CRITICAL INSTRUCTIONS FOR TABLE LAYOUT:

1. **Header Analysis:**
   - Focus on the FIRST ROW (header row) to identify column names/property names
   - Each column header defines what data that column contains

2. **Primary Key Identification:**
   - Determine which column(s) should be used as the first-level identifier
   - Primary key columns are typically the leftmost columns that group related rows together
   - Look for columns where values repeat or are empty across multiple rows - these indicate grouped data
   - Rows with the same (or empty) primary key values belong to the same top-level entry

3. **Hierarchy Construction:**
   - Top level: Values from primary key columns
   - Nested levels: Values from remaining columns, grouped under their primary key entry
   - Use indentation to show parent-child relationships

4. **Empty Value Handling:**
   - Empty cells in primary key columns indicate continuation of the previous entry
   - Empty cells in other columns can be omitted or shown as empty
   - Treat consecutive rows with empty primary keys as sub-items of the last non-empty primary key

5. **Nested Content Preservation:**
   - Preserve [START_TABLE_CONTENT]...[END_TABLE_CONTENT] markers exactly as-is
   - Preserve [START_IMAGE_PATH]...[END_IMAGE_PATH] markers exactly as-is

6. **Multi-level Hierarchy:**
   - After primary key, determine if remaining columns have their own hierarchy
   - Some columns may be grouping columns (second-level keys)
   - Others may be detail/value columns (leaf nodes)"""

        user_prompt = fr"""Table data with headers:

{table_data}

ANALYSIS STEPS:
1. Identify the header row and extract all column names
2. Analyze the data pattern to determine which columns are PRIMARY KEYS:
   - Which columns have repeating or empty values across multiple rows?
   - Which columns appear to group related data together?
3. Identify remaining columns as detail/attribute columns
4. Group rows by primary key values
5. Create hierarchical structure with appropriate indentation

PROCESSING RULES:
- Cell data is wrapped in 2 consecutive `|`
- First row is the header (column names)
- Empty values in primary key columns mean "same as above"
- Preserve [START_TABLE_CONTENT]...[END_TABLE_CONTENT] markers exactly as-is
- Preserve [START_IMAGE_PATH]...[END_IMAGE_PATH] markers exactly as-is
- Use indentation to show hierarchy depth (each level adds more spaces)
- Do not remove any table data (both header and content), just reformat only.

OUTPUT FORMAT:
```
PrimaryColumn: value
     SecondaryColumn: value
     SecondaryColumn: value
          DetailColumn: value
               AttributeColumn: value
               AttributeColumn: value
```

Return the complete flattened hierarchical structure with all entries organized logically."""

    else:  # zone layout
        system_prompt = """You are a zone layout analyzer that converts table markdown into hierarchical entries.

Your task:
1. Analyze the CONTENT to identify property names (zone layouts don't have traditional column headers)
2. Identify sections and hierarchical relationships
3. Create structured output showing the property hierarchy

CRITICAL INSTRUCTIONS FOR ZONE LAYOUT:

1. **Property Names Location:**
   - Property names are in the LEFTMOST NON-EMPTY cell of each row
   - The VALUE for that property is in the next non-empty cell(s) to the right

2. **Ignore Empty Columns:**
   - Many columns are empty (used for spacing/layout only)
   - Skip all empty cells when identifying values
   - Only process non-empty cells

3. **Handle Nested Content:**
   - Some property values may contain nested tables marked with [START_TABLE_CONTENT]...[END_TABLE_CONTENT]
   - Some property values may contain images marked with [START_IMAGE_PATH]...[END_IMAGE_PATH]
   - Preserve these markers exactly as-is in the output

4. **Section Detection:**
   - When a property name repeats, it typically indicates a NEW section/entry starting
   - Group properties that appear consecutively as belonging to the same section
   - Use context and semantic meaning to determine logical groupings

5. **Hierarchy Determination:**
   - Analyze the data to identify parent-child relationships between properties
   - Properties that provide high-level categorization are typically top-level
   - Properties that provide details or specifications are typically nested under relevant parents
   - Properties with numeric labels (1, 2, 3...) or bullets are usually list items under a parent
   - Use semantic meaning and positioning to infer hierarchy

6. **Multi-column Values:**
   - A single property's value may span multiple columns
   - Concatenate all non-empty values from columns to the right of the property name
   - Stop when reaching another row or clear section boundary"""

        user_prompt = fr"""Zone layout data (contains many empty columns - ignore them):

{table_data}

ANALYSIS STEPS:
1. For each row, identify the LEFTMOST non-empty cell as the potential property name
2. Extract all subsequent non-empty cells in that row as the property VALUE
3. Recognize when property names repeat to detect new sections/entries
4. Determine parent-child relationships based on semantic meaning and context
5. Create hierarchical structure with appropriate indentation

PROCESSING RULES:
- Cell data is wrapped in 2 consecutive `|`
- Skip all empty cells/columns completely
- Only extract and process non-empty content
- Preserve [START_TABLE_CONTENT]...[END_TABLE_CONTENT] markers exactly as-is
- Preserve [START_IMAGE_PATH]...[END_IMAGE_PATH] markers exactly as-is
- Group related properties under logical parent properties
- Use indentation to represent hierarchy depth (each level adds more spaces)
- Do not remove any table data (both header and content), just reformat only.

OUTPUT FORMAT:
```
PropertyName: value
     SubProperty: value
     SubProperty: value
          NestedProperty: value
               DetailProperty: value
```

Return the complete flattened hierarchical structure with all properties organized logically."""
        
    return await call_llm(
        llm,
        llm_params_fn,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=tools,
        tool_choice=tool_choice,
    )
