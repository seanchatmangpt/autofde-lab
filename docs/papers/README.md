# ForwardBench / AutoFDE research corpus

This directory is an **EXPLORE** literature surface for ForwardBench, cloud gyms, real-time process intelligence, IaC verification, incident response, enterprise workflows, and agent evaluation. Inclusion is not admission and does not establish that AutoFDE reproduces a paper's results.

## Retrieval standing

The local creation capsule could not resolve `arxiv.org`, so PDF acquisition was routed through a branch-scoped GitHub Actions capsule. The exact workflow fetched and `%PDF-`-validated every manifest paper, then generated `pdf/SHA256SUMS` before committing the PDFs. Paper reproduction remains `NOT_REPRODUCED`; retrieval standing is `PDF_FETCHED_SHA256_VERIFIED`. `fetch-pdfs.sh` remains the deterministic local replay path for a network-enabled capsule.

## Core clusters

- Cloud / IT operations: ITBench, AIOpsLab, microservice diagnosis, Kubernetes RCA, ARFBench, Agentic NetOps/AIOps.
- IaC: Multi-IaC-Eval, verifier-first Terraform, security-first Terraform.
- Security response: SIR-Bench and SecRespond.
- Process / enterprise dynamics: PM-LLM-Benchmark, process-mining evaluation, World of Workflows, WorkArena/WorkArena++, EnterpriseBench, CRMArena-Pro.
- Agent environments / interoperability: CUBE, ToolSandbox, tau-bench, OSWorld, AgentBench.
- Generated/evolving gyms: Continuous Benchmark Generation, Frontier-Eng, BenchBench, R2E-Gym, SciAgentArena.

Use `manifest.toml` as the machine-readable index. Each `<arxiv-id>.md` file contains the canonical record/PDF links, standing, tags, and the reason the paper matters to AutoFDE/ForwardBench.
