# 003 Single MCP

Status: implemented-needs-runtime-verification
Depends-on: 001, 002

## Goal

Expose the five read-only sales tools through one MCP Streamable HTTP service.

## Done when

- MCP exposes exactly the five v1 read tools.
- Tool responses are JSON.
- MCP is the only component that accesses MySQL and the knowledge base.

## Verification

- MCP registry exposes exactly the five required tool names.
- HTTP runtime verification is pending on Docker-backed MySQL availability.
