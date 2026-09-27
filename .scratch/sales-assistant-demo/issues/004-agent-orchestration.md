# 004 Agent orchestration

Status: implemented-needs-runtime-verification
Depends-on: 003

## Goal

Implement the LangChain single Agent, MCP client calls, customer-selection state, fixed workflow, schema validation, retry, persistence, and streaming events.

## Done when

- Agent handles missing, unknown, unique, and ambiguous customer names.
- Agent calls MCP tools instead of direct database functions.
- Final output validates against the v1 schema.
- Invalid model JSON is retried once.
- Sessions, messages, tool calls, and analysis results are persisted.
- No write or email tool is called.

## Verification

- Python compile check passed.
- Missing-customer, ambiguous-customer, numbered-selection, and structured-fallback smoke checks passed.
- Real MCP/MySQL end-to-end verification is pending.
