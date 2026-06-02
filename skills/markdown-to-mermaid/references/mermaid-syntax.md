# Mermaid Syntax Quick Reference

## Flowchart
```
flowchart TD
  A[Start] --> B{Decision}
  B -->|Yes| C[Do Thing]
  B -->|No| D[Stop]
```

## Sequence
```
sequenceDiagram
  participant User
  participant System
  User->>System: Request
  System-->>User: Response
```

## State
```
stateDiagram-v2
  [*] --> Idle
  Idle --> Running : start
  Running --> [*] : stop
```

## Gantt
```
gantt
  title Example
  dateFormat YYYY-MM-DD
  section Phase 1
  Task A :done, a1, 2025-01-01, 2025-01-05
  Task B :active, a2, 2025-01-06, 2025-01-10
```

## Mindmap
```
mindmap
  root((Root))
    Branch A
      Leaf A1
    Branch B
```
