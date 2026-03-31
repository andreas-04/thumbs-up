# ThumbsUp System Diagrams

Architectural and flow diagrams for the ThumbsUp secure file sharing system. Source files are in `diagrams/` as `.mmd` (Mermaid) files with rendered PNGs in `diagrams/png/`.

## Diagrams

| # | Diagram | Source | PNG |
|---|---------|--------|-----|
| 1 | System Architecture Overview | [01-system-architecture.mmd](diagrams/01-system-architecture.mmd) | [PNG](diagrams/png/01-system-architecture.png) |
| 2 | Authentication Flow | [02-authentication-flow.mmd](diagrams/02-authentication-flow.mmd) | [PNG](diagrams/png/02-authentication-flow.png) |
| 3 | Role-Based Access Control (RBAC) | [03-rbac.mmd](diagrams/03-rbac.mmd) | [PNG](diagrams/png/03-rbac.png) |
| 4 | Layered Permission Resolution | [04-permission-resolution.mmd](diagrams/04-permission-resolution.mmd) | [PNG](diagrams/png/04-permission-resolution.png) |
| 5 | Certificate Lifecycle & mTLS Flow | [05-certificate-mtls.mmd](diagrams/05-certificate-mtls.mmd) | [PNG](diagrams/png/05-certificate-mtls.png) |
| 6 | File Access Control Flow | [06-file-access-control.mmd](diagrams/06-file-access-control.mmd) | [PNG](diagrams/png/06-file-access-control.png) |
| 7 | User Onboarding & Approval Workflow | [07-user-onboarding.mmd](diagrams/07-user-onboarding.mmd) | [PNG](diagrams/png/07-user-onboarding.png) |
| 8 | Database Entity Relationship Diagram | [08-database-erd.mmd](diagrams/08-database-erd.mmd) | [PNG](diagrams/png/08-database-erd.png) |

## Rendering PNGs

To re-render all diagrams after editing a `.mmd` file:

```bash
cd docs/diagrams
for f in *.mmd; do
  mmdc -i "$f" -o "png/${f%.mmd}.png" -b transparent -w 2048
done
```

Requires [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`npm install -g @mermaid-js/mermaid-cli`).

---

*Document Version: 2.1*
*Last Updated: March 2026*
