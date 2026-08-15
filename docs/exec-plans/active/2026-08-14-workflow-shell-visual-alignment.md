# 001#全專案建立頁與工作頁視覺一致性改版

Plan status: active

## Done state

- Supplier-event create pages and warehouse NCR creation use the shared
  `CreateWorkflowShell`: one command row, inline feedback and one scroll owner.
- Supplier-event/NCR list filters use `QueryWorkflowShell`; supplier-event/NCR
  dashboards use `AnalyticsWorkflowShell` without crossing data boundaries.
- Dialog edit/preview actions remain in fixed dialog footers; no data contract,
  service, export or navigation semantics change.

## Verification gates

- Focused structural tests cover page scroll/action ownership, route behavior,
  NCR continuous-entry preservation and shared query/analytics shell placement.
- Native Windows Qt probes cover `event-create`, `form-density`, `event-list`,
  `ncr-tracker`, `stats-stress`, `ncr-stats`, `main`, `master-data`, empty states
  and popup paths at 1.0/1.25/1.5 scale.
- `scripts\verify.ps1` and `scripts\harness_check.ps1` run after source and
  documentation changes; unavailable native evidence is reported as not verified.
