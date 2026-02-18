# Incident Response

## When to Use
Any production issue that affects users: downtime, data errors, security breach, performance degradation beyond SLA (P95 > 500ms or uptime < 99.5%).

## Preconditions
- On-call person has AWS Console access, CloudWatch access, and ECS deploy permissions.
- Communication channel available (Slack/Telegram group for the team).
- `runbook-prod.md` open as reference for diagnostic commands.

---

## Severity Levels

| Severity | Definition | Response Time | Examples |
|----------|-----------|---------------|---------|
| **SEV-1** | Service down or data breach | Immediate (< 15 min) | All APIs returning 500, tenant data leaked, auth bypass |
| **SEV-2** | Major feature broken | < 1 hour | AI chat down, orders not saving, notifications not sending |
| **SEV-3** | Minor degradation | < 4 hours | Slow API responses, dashboard data delayed, cosmetic UI bug |

---

## Steps

### Phase 1: Detect & Triage (0–15 min)

1. **Acknowledge the alert** in the team channel. State: "Investigating [alarm name / user report]."
2. **Determine severity** using the table above.
3. **Quick diagnostics** (see `runbook-prod.md`):
   ```bash
   curl https://api.yourdomain.com/api/v1/health
   aws ecs describe-services --cluster saas-prod --services saas-backend saas-worker --region me-south-1
   aws logs tail /prod/backend --since 10m --region me-south-1 --filter-pattern 'ERROR'
   ```
4. **Identify scope**: one tenant or all tenants? One endpoint or all?

### Phase 2: Mitigate (15–60 min)

Goal: restore service, even if it means a temporary workaround.

| Situation | Mitigation |
|-----------|-----------|
| Bad deploy causing errors | Rollback ECS to previous task definition |
| Database overloaded | Scale down ECS tasks to reduce connections, enable RDS Proxy if available |
| Redis down | ElastiCache failover (automatic); if manual: restart replication group |
| AI provider down | Switch provider via SSM config (see `runbook-prod.md` Scenario E) |
| Security breach (SEV-1) | Rotate affected secrets immediately. If auth bypass: disable Cognito app client, investigate scope |
| Single tenant issue | Investigate tenant-specific data; if needed, temporarily suspend tenant while fixing |

5. **Communicate**: post update in team channel: "Mitigated by [action]. Service restored at [time]. Investigating root cause."

### Phase 3: Resolve (1–24 hours)

6. **Root cause analysis**: identify the actual cause (not just the symptom).
7. **Fix**: implement and deploy the fix through normal release process (or hotfix if urgent).
8. **Verify**: run relevant QA checklist items (see `qa-checklist.md`).
9. **Communicate**: "Resolved. Root cause was [X]. Fix deployed at [time]."

### Phase 4: Post-Mortem (within 48 hours)

10. **Write post-mortem** using the template below.
11. **Share** with the team.
12. **Create action items** as backlog tasks.
13. **Update runbooks** if a new scenario was encountered.

---

## Post-Mortem Template

```markdown
# Incident Post-Mortem: [Title]

**Date**: YYYY-MM-DD
**Severity**: SEV-X
**Duration**: HH:MM (from detection to resolution)
**Author**: [name]

## Summary
One-paragraph description of what happened.

## Timeline (UTC)
- HH:MM — Alert fired / user reported
- HH:MM — On-call acknowledged
- HH:MM — Root cause identified
- HH:MM — Mitigation applied
- HH:MM — Fix deployed
- HH:MM — Confirmed resolved

## Root Cause
What actually broke and why.

## Impact
- Users affected: [count or "all tenants" / "single tenant"]
- Duration of impact: [minutes]
- Data loss: [none / describe]

## Mitigation
What was done to restore service before the full fix.

## Fix
What code/config change resolved the root cause.

## Action Items
- [ ] [Action 1] — owner: [name], deadline: [date]
- [ ] [Action 2] — owner: [name], deadline: [date]

## Lessons Learned
What we'd do differently next time.
```

---

## Rollback
Rollback procedures are in `runbook-prod.md` (ECS rollback, Alembic downgrade, Vercel rollback).

---

## Post-Incident Notes
- Every SEV-1 and SEV-2 incident MUST have a post-mortem within 48 hours.
- SEV-3 incidents: post-mortem optional but encouraged if the fix was non-trivial.
- Action items from post-mortems are tracked in the backlog with `incident` label.
- Review incident history quarterly to identify patterns.
