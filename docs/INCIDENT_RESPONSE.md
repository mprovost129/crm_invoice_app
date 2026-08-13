# Incident Response Runbook

Last reviewed: 2026-08-12

This is the minimum operational procedure. Replace role placeholders and contact channels
before launch; do not put credentials or private customer data in this document.

## Severity

- **SEV-1:** confirmed data exposure, account takeover, cross-tenant access, incorrect money
  movement, unrecoverable primary outage, or material data loss.
- **SEV-2:** major workflow/provider outage, growing queue/backlog, failed reconciliation,
  or degraded access affecting multiple customers without confirmed exposure/loss.
- **SEV-3:** contained defect or single-customer issue with a safe workaround.

## First 15 Minutes

1. Assign incident commander, operations lead, communications lead, and scribe. One person
   may hold multiple roles initially, but the commander coordinates rather than debugging.
2. Record start time, detector, affected environment/version, request IDs, symptoms, and
   known customer/business scope. Never copy raw public tokens, secrets, card data, or full
   webhook payloads into chat/tickets.
3. Preserve evidence: immutable image/version, logs, relevant row IDs, provider event IDs,
   queue counts, migration status, and reconciliation output.
4. Contain the smallest safe surface:
   - disable affected Plan features to stop new online payment entry;
   - remove configured Stripe Price IDs to stop new subscription checkout;
   - pause a faulty worker/scheduler while leaving durable inbox/outbox rows intact;
   - route traffic to a compatible known-good image when schema/job formats permit.
5. Do not delete or edit issued documents, payments, reversals, webhook events, outbox
   events, or connected-account identifiers to make an alert disappear.

## Investigation

- Establish a timeline in UTC and preserve business-local timestamps where relevant.
- Determine whether this is availability, confidentiality, integrity, financial, provider,
  deployment, credential, or data-recovery impact.
- Compare application ledger state with provider state using the reconciliation commands.
- For cross-tenant suspicion, stop the writer and test adjacent list/detail/action/export
  paths before restoring service.
- For a suspected secret leak, revoke/rotate at the provider, invalidate dependent sessions
  or links, update platform-managed configuration, and redeploy; never paste the old value.
- For payment issues, determine charge ownership/account context before refunding or
  communicating. Provider redirects and screenshots are not payment evidence.

## Communication

- Give factual impact, affected period/scope, current containment, customer action, and next
  update time. Do not speculate about cause or exposure.
- Security/privacy notifications must follow approved legal and jurisdictional guidance.
- Maintain an internal update cadence of 30 minutes for SEV-1 and 60 minutes for SEV-2
  until stable, even when there is no material change.

## Recovery and Exit

1. Implement a reviewed forward fix or compatible rollback.
2. Apply/replay durable work in bounded batches and observe failures.
3. Run Django readiness/deploy checks, launch gate, communication/provider health, ledger
   reconciliation, provider reconciliation when enabled, and the affected E2E workflow.
4. Confirm alerts, queues, error rate, latency, database health, customer-visible state,
   and provider state remain stable for the agreed observation window.
5. Incident commander declares recovery and records residual risk/follow-up owners.

## Post-Incident

Within five business days for SEV-1/2, produce a blameless review covering timeline,
impact, detection, contributing conditions, containment/recovery, what worked, and concrete
actions with owners/dates. Update tests, runbooks, monitoring, and DECISIONS when the fix
changes a product or architecture rule.

