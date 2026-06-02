# Daytona Diagram

## Evidence Inputs
- Task 1 CLI and Toolbox probes
- Task 2 Port 18791 discovery
- Task 3 Gateway RPC and tools catalog

## Capability Findings
- Daytona Toolbox transport is verified
- Port 18791 is not a messaging API in this setup
- HTTP hooks push path not active here POST returns 405

## Decision
- Replace daytona exec transport with Toolbox API
- Keep mailbox pull semantics

## Implementation Delta
- Use POST process execute
- Use POST files upload
- Use GET files download
