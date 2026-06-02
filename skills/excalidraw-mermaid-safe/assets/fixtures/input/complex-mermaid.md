# Existing Diagram

```mermaid
flowchart TD
  A[Start from [docs](https://example.com/docs)]
  B[POST https://api.example.com/v1/jobs]
  C[Decision: keep importer]
  A -- uses docs --> B
  B --> C
  style A fill:#000,color:#fff
  linkStyle 0 stroke:#f00
```
