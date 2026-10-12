# Incident Response

## Severity

| Sev | Azure Monitor label | Definition (for this demo) | Response |
|---|---|---|---|
| Sev1 | Error | Core journeys down for most requests (e.g. DB down, 5xx > 50%) | Start immediately; incident commander assigned |
| Sev2 | Warning | Partial impact: checkout failing, 5xx > 5%, SLO burn rate > 14× | Start within 15 min |
| Sev3 | Informational | Degradation within SLO: latency elevated, single dependency degraded | Next working session |
| Sev4 | Verbose | No user impact (stale alert, noisy signal) | Ticket |

(Azure Monitor's Sev0 "Critical" is reserved; we don't use it in drills.)

## Roles (map to the four rotating team roles)

| Incident role | Default team role | Does |
|---|---|---|
| Incident Commander (IC) | SRE Agent & Incident engineer | Owns the timeline, decides, **approves or denies agent actions** (must hold SRE Agent Administrator) |
| Operations lead | App & Deploy engineer | Runs diagnostics and mitigations |
| Observability lead | Observability & KQL engineer | Queries telemetry, validates the agent's evidence |
| Scribe / comms | Security, Testing & Docs engineer | Timeline, status updates, post-incident report |

## Lifecycle

1. **Detect:** alert fires, a smoke test fails, or a user reports a problem. Note the time (UTC).
2. **Triage (≤ 10 min):**
   - Check current state: `/health/ready`, error rate and p95 for the last 15 minutes.
   - Classify severity. Identify affected endpoints.
   - Check *what changed*: deployments or revisions, fault audit log (`event=fault_enabled`), config.
3. **Investigate:** follow the matching runbook. Ask Azure SRE Agent to investigate *in parallel*,
   then **verify its evidence** against telemetry. Never act on an unverified conclusion.
4. **Mitigate:** prefer the least risky reversible action (reset fault → roll back revision →
   restart → scale). Actions follow [../agent-context/RESOURCE_BOUNDARIES.md](../agent-context/RESOURCE_BOUNDARIES.md).
5. **Verify recovery:** readiness 200 `ready`, smoke test passes, error rate back to baseline for
   ≥ 10 min. **A silenced alert is not a recovery.**
6. **Close:** report error-budget impact ([SERVICE_LEVELS.md](SERVICE_LEVELS.md)).
7. **Post-incident review** within 2 working days (template below).

## Working with Azure SRE Agent during an incident

- The agent investigates and recommends. **Humans decide.** Response plans run in **Review** mode.
- Ask for evidence: "Show the query and the result that supports this."
- Ask for alternatives: "What else could cause this? What evidence would rule it out?"
- Before approving a write: check it against the runbook, its blast radius, and its rollback.
- Record the agent's thread link in the incident timeline.

## Post-incident report template

```markdown
# Incident <ID>: <one-line summary>
- Severity / Status:
- Detected (UTC): / Mitigated (UTC): / Resolved (UTC):
- Detection source: alert | smoke test | user | agent
## Impact
- Affected journeys/endpoints:
- Failed requests: N of M (X%). Error budget consumed: Y% of 28-day budget
## Timeline (UTC)
| time | event | who/what |
## Root cause
- Cause (with evidence: query + result):
- Why symptoms appeared where they did:
## Resolution
- Action taken, approver, verification evidence:
## What went well / what went poorly
## Agent assessment
- Was the agent's RCA correct? Evidence quality? Any unsafe or unsupported suggestions?
## Action items (owner, due date)
```
