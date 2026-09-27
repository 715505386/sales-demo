# 006 Runtime and manual acceptance

Status: implemented-needs-runtime-verification
Depends-on: 001, 003, 004, 005

## Goal

Provide configuration templates, startup orchestration, README instructions, and manual acceptance evidence.

## Done when

- MySQL, MCP, Agent, and Streamlit have documented startup commands.
- A single local launcher starts the three Python processes after MySQL is available.
- README matches the read-only v1 behavior.
- Manual acceptance scenarios are executed or explicitly reported with any infrastructure gap.

## Verification

- Startup commands and one-click launcher are implemented.
- Docker Desktop Linux Engine was unavailable during this implementation session.
