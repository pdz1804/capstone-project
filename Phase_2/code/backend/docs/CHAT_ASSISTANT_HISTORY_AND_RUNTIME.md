# Chat Assistant History and Runtime

This document describes the current chat assistant implementation, including persistent history, API contracts, DynamoDB schema, and runtime mode switching.

## Scope

- Session-based chat with persistent history
- Frontend session management UX (rename, pin, delete, pagination)
- Runtime switching between local Strands and Bedrock AgentCore runtime

## Backend API

Base prefix: `/api/chat`

### Stream

- `POST /api/chat/stream`
- Request body fields:
  - `query` (required)
  - `session_id` (optional; generated if missing)
  - `persona` (optional)
  - `education_description` (optional)
- Response: Server-Sent Events with event payload types:
  - `session`
  - `status`
  - `tool_trace`
  - `token`
  - `suggestions`
  - `done`
  - `error`

### History

- `GET /api/chat/sessions?limit=<n>&cursor=<cursor>`
- `POST /api/chat/sessions`
- `PATCH /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`
- `GET /api/chat/sessions/{session_id}/messages?limit=<n>&cursor=<cursor>&newest_first=<bool>`

## DynamoDB schema

### Sessions table

- Table name (default): `chatbot-session`
- PK: `user_id` (string)
- SK: `session_id` (string)

Common attributes:

- `title`
- `pinned`
- `message_count`
- `created_at`
- `updated_at`
- `last_message_at`
- `last_message_preview`
- `last_message_role`

### Messages table

- Table name (default): `chatbot-messages`
- PK: `session_id` (string)
- SK: `message_id` (string)

Common attributes:

- `user_id`
- `role`
- `content`
- `created_at`
- `traces` (optional)
- `suggestions` (optional)

## Frontend behavior

Chat history panel behavior:

- Compact session list (Gemini-like rail)
- Create new chat
- Rename chat title
- Pin/unpin chat
- Delete session
- Pagination controls
- History sync toggle (on/off)

When history sync is off, chat still runs, but session history APIs are skipped.

## Runtime mode switch

### Local mode (default)

- `CHAT_AGENT_RUNTIME=local`
- Uses local Strands runtime adapter in `backend/agent/strands_chat_runtime.py`

### AgentCore runtime mode

- `CHAT_AGENT_RUNTIME=agentcore-runtime`
- `AGENTCORE_RUNTIME_ARN=<deployed runtime arn>`
- `AGENTCORE_REGION=<aws region>`

Invocation path uses boto3 `bedrock-agentcore`:

- `invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload)`

## Agent runtime files

- `backend/agent/strands_chat_runtime.py`
- `backend/agent/agentcore_runtime_entrypoint.py`
- `backend/agent/requirements-agentcore-runtime.txt`

## Notes

- History API is user-scoped via `X-User-Id` and auth context.
- `OPTIONS` requests in logs are expected browser CORS preflight behavior.
- Runtime mode is configuration-only; no route code changes are required to switch modes.
