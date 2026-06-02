# Workflow

The skill composes three layers:

- browser control: Browser plugin, Playwright Interactive, or Playwright CLI
- observation: DOM/accessibility snapshot, screenshot, and overlay semantic map
- agent policy: intent resolution, ranking, action, verification, and recovery

```mermaid
flowchart LR
  U["User intent"] --> N["Overlay Browser Navigator"]

  subgraph B["Browser control"]
    B1["In-app browser"]
    B2["Persistent Playwright"]
    B3["Playwright CLI"]
  end

  subgraph O["Observation inputs"]
    O1["DOM / accessibility snapshot"]
    O2["Viewport screenshot"]
    O3["Overlay semantic map"]
  end

  subgraph S["Overlay signals"]
    S1["Landmarks"]
    S2["Headings"]
    S3["Interactive targets"]
    S4["Accessible names"]
    S5["Hit boxes"]
    S6["Focus order"]
  end

  subgraph D["Decision loop"]
    D1["Resolve intent"]
    D2["Rank candidates"]
    D3["Check risk"]
    D4["Choose action"]
  end

  subgraph A["Act and verify"]
    A1["Click / type / scroll / navigate"]
    A2["Observe changed state"]
    A3["Verify goal"]
    A4["Recover"]
  end

  N --> B1
  N --> B2
  N --> B3
  B1 --> O1
  B2 --> O1
  B3 --> O1
  B1 --> O2
  B2 --> O2
  B3 --> O2
  B1 --> O3
  B2 --> O3
  B3 --> O3
  O3 --> S1
  O3 --> S2
  O3 --> S3
  O3 --> S4
  O3 --> S5
  O3 --> S6
  O1 --> D1
  O2 --> D1
  S1 --> D2
  S2 --> D2
  S3 --> D2
  S4 --> D2
  S5 --> D3
  S6 --> D3
  D1 --> D2
  D2 --> D3
  D3 --> D4
  D4 --> A1
  A1 --> A2
  A2 --> A3
  A3 -->|"success"| Z["Done"]
  A3 -->|"not matched"| A4
  A4 --> O1
  A4 --> O2
  A4 --> O3
```

Use this as a workflow map, not as a mandatory artifact to produce on every
navigation task.

