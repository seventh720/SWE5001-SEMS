# Local Kubernetes acceptance — 2026-10-24

Result: **passed**. This run validates deployment and business correctness on a disposable local Kubernetes cluster. It does not measure EKS capacity, scaling benefit, node availability, recovery time or cloud rollback.

## Environment and build

- kind 0.33.0, Kubernetes 1.36.4, Linux arm64, one local node backed by Docker Desktop. The two Admission Pods share that node; there is no independent-host availability result.
- Namespace/context: `sems-local` / `kind-sems-local`. PostgreSQL has its own PVC and credentials, separate from the existing Compose stack and Lightsail. The five Deployments run seven Pods in total including PostgreSQL: Identity ×1, Catalog ×1, Admission ×2, Web ×1, Gateway ×1, PostgreSQL ×1.
- Source base: `d3002d10a6f515b14f2013fc89f8805837b1f8ec` with uncommitted Kubernetes configuration/tooling changes. The rendered local manifest SHA-256, Pod identities and actual runtime image identifiers are recorded in [summary.json](summary.json). These local image identifiers are not a published EKS release lock.
- Java build/tests: Oracle JDK 21.0.12; all **84** tests passed: Identity 32, Catalog 35, Admission 17. See [backend-build.txt](backend-build.txt).
- Frontend TypeScript/Vite build passed using Node.js 24.21.0; frontend component tests were not rerun in this deployment-only run. See [frontend-build.txt](frontend-build.txt).
- Six images were rebuilt under the independent `sems-k8s-local` project and loaded into kind. The current CI image security/promotion gates still need to run for any future published release.

The first Maven attempt inside the sandbox could not initialize Mockito's inline agent because JVM attachment was restricted. It did not complete the suite. The same Java 21 verification succeeded outside that restriction; the saved build log is the completed successful attempt.

## Business and consistency results

The [reusable runner](../../../scripts/k8s/local-acceptance.py) opens its own temporary loopback port-forwards and closes them on completion. Ordinary flows go through Gateway; concurrency requests are deliberately divided between the two identified Admission Pods. Fresh accounts and events are created for this run. Credentials, JWTs and ticket credentials are omitted from saved results.

| Check | Observed result |
|---|---|
| Routing/readiness | Web and all health endpoints returned 200; the public internal-service path returned 404 |
| Identity/organization foundation | Registration, login, RSA signature rejection, grants, organization isolation, draft persistence/validation and concurrent editing passed |
| Publication/booking | Public event discovery, booking, ownership isolation, same-key replay and changed-payload rejection passed |
| Same request key on two Pods | 20 requests, 10 sent to each Pod; one distinct booking. Together with the earlier two-place booking, the reserved count was 3 |
| Last ten places on two Pods | 100 distinct requests, 50 sent to each Pod; **10 HTTP 200, 90 HTTP 409**. Database reserved / confirmed quantity / valid tickets = **10 / 10 / 10** |
| Concurrent check-in | Unassigned organizer rejected with 403; after assignment, ten checks across both Pods produced one first check-in and one shared check-in timestamp |
| Personal cancellation | Cancelling the two-place booking twice released inventory once; reserved count remained 1 for the other booking |
| Whole-event cancellation | Reserved / confirmed bookings / valid tickets / retained checked-in tickets / cancellation receipts = **0 / 0 / 0 / 1 / 1**; repeated cancellation remained terminal |
| Database ownership | Six cross-schema USAGE checks and three public CREATE checks denied; an actual Catalog-role query of Identity data was denied |

Raw group results: [kubernetes-acceptance.txt](kubernetes-acceptance.txt). Structured counts and timestamps: [summary.json](summary.json). These are bounded correctness checks, not a sustained-load or throughput measurement.

## Initial startup and current state

The first simultaneous deployment created the database and backends together. Each Java Pod exited once while the PostgreSQL headless Service had no ready DNS address (`UnknownHostException: postgres` during Flyway initialization). Kubernetes restarted the Pods and all became ready. The startup diagnostics are retained in [initial-startup.txt](initial-startup.txt); [pod-state.json](pod-state.json) records all seven ready Pods and their restart counts. No liveness-based database-outage recovery or zero-restart cold-start result is claimed.

The local cluster and disposable fixtures were retained for inspection. The kubeconfig and bootstrap login remain only under ignored `.secrets/k8s-local/`. No AWS resources were created, no existing Compose containers were restarted, and no Lightsail data or DNS was changed.

Reproduction commands and the separate EKS template are in the [Kubernetes guide](../../kubernetes.md). EKS network/IAM/RDS/ALB integration, independent service release, controlled scaling, failure recovery and compatible rollback remain separate cloud acceptance work.
