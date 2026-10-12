# Security Design

Policy summary is in [../SECURITY.md](../SECURITY.md). This file covers the design.

## Data
- Data is synthetic: customer IDs are free text like `cust-001`, there are no names, payment
  cards or PII. **Do not** enter real personal data.
- Money is integer cents. There is no real payment processing.

## Identities [PLANNED-AZURE: finalised in Phase 6]

| Principal | Type | Scope | Access | Why |
|---|---|---|---|---|
| Architect (you) | Entra user | subscription | Owner | Build and administer. Also **SRE Agent Administrator** (approves agent actions) |
| Team members | Entra users | `rg-sredemo-app` and agent | Reader/Contributor on the RG as needed; SRE Agent Standard User (or Author) | Least privilege by role |
| `id-orders-api` | User-assigned managed identity | ACR, Key Vault, PostgreSQL | AcrPull; Key Vault Secrets User; PostgreSQL role with table rights only | App needs no secrets for these |
| SRE Agent identity | Agent's UAMI (auto-created) | `rg-sredemo-app` | Reader + Monitoring Reader + Log Analytics Reader (Reader level) | Investigate. Writes go through OBO approval |
| SRE Agent (alerts) | same | subscription | Monitoring Contributor | Required to acknowledge/close Azure Monitor alerts (documented product requirement) |
| GitHub Actions | Entra app + federated credential (OIDC) | `rg-sredemo-app` | Contributor on RG (M11) | Deploy without a stored client secret |

## Controls
- **No credentials in code or git.** `.env` is ignored. The CI uses throwaway values. Azure uses managed identity.
- **Fault API**: disabled by default, token required, constant-time comparison, audit-logged,
  payment-stub admin reachable only inside the environment.
- **Container**: non-root user, slim base image, no shell tools added.
- **Network**: only orders-api is public. payment-stub is internal. PostgreSQL allows Azure services
  only (private networking is out of scope for cost; revisit for production).
- **Agent guardrails**: Reader permission level, Review run mode, tool access policies, scope
  limited to `rg-sredemo-app`, see [../agent-context/RESOURCE_BOUNDARIES.md](../agent-context/RESOURCE_BOUNDARIES.md).

## Known gaps (accepted for a demo)
- Public PostgreSQL endpoint (firewall-restricted) instead of private endpoint/VNet.
- The fault token is shared by orders-api and payment-stub.
- No WAF or rate limiting on the public endpoint.
