# 005 Streamlit UI

Status: implemented-needs-runtime-verification
Depends-on: 004

## Goal

Build the chat UI with streaming progress, candidate selection conversation, structured result rendering, and collapsible tool details.

## Done when

- Sales can submit a question and see progress.
- Candidate lists and follow-up replies work in the same session.
- Final JSON is rendered into readable sections.
- Tool calls are collapsed by default and expandable.

## Verification

- Streamlit module compile check passed.
- Browser-level verification is pending because the Agent/MySQL runtime could not start.
