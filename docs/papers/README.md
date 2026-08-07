# ForwardBench / AutoFDE research corpus

This directory is an **EXPLORE** literature surface for ForwardBench, cloud gyms, real-time process intelligence, IaC verification, incident response, enterprise workflows, and agent evaluation. Inclusion is not admission and does not establish that AutoFDE reproduces a paper's results.

## Retrieval standing

The creation capsule could not resolve `arxiv.org` over local DNS, so raw PDF bytes were not fetched. The paper files here are Markdown capsules converted from canonical arXiv HTML/abstract metadata plus original AutoFDE relevance notes. Every paper records `PDF_NOT_FETCHED|NOT_REPRODUCED`. `fetch-pdfs.sh` records the deterministic canonical PDF acquisition path for a network-enabled capsule and was syntax-validated locally, not executed.

## Core clusters

- Cloud / IT operations: ITBench, AIOpsLab, microservice diagnosis, Kubernetes RCA, ARFBench, Agentic NetOps/AIOps.
- IaC: Multi-IaC-Eval, verifier-first Terraform, security-first Terraform.
- Security response: SIR-Bench and SecRespond.
- Process / enterprise dynamics: PM-LLM-Benchmark, process-mining evaluation, World of Workflows, WorkArena/WorkArena++, EnterpriseBench, CRMArena-Pro.
- Agent environments / interoperability: CUBE, ToolSandbox, tau-bench, OSWorld, AgentBench.
- Generated/evolving gyms: Continuous Benchmark Generation, Frontier-Eng, BenchBench, R2E-Gym, SciAgentArena.

Use `manifest.toml` as the machine-readable index. Each `<arxiv-id>.md` file contains the canonical record/PDF links, standing, tags, and the reason the paper matters to AutoFDE/ForwardBench.
