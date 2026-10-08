# SA2A universal computation boundary

SA2A treats computation as a producer of typed candidate assertions, not as a source of authority.

The producer may be an ONNX model, GNN, scikit-learn estimator, Nx/Axon model, LLM, FOND/HDDL solver, SPARQL query, rule engine, WASM module, ordinary function, or human. The downstream contract is the same:

canonical subject -> computation artifact -> SemanticClaim / PlanningAdvice -> admission / formal planner -> SELECT -> CONSTRUCT -> authority -> BRCE -> DO -> receipt.

## Computational ABI vs semantic ABI

ONNX or another runtime format answers how a computation executes. SA2A answers what the output means, which exact subject and projection produced it, what evidence class it belongs to, and what standing it has.

A portable model is represented by ComputationArtifact. Runtime is part of its descriptor identity, but capability identity is independent of runtime so one capability can be provided by ONNX, Nx, PyTorch, scikit-learn, a rule, or another qualified implementation.

Every SemanticClaim emitted here is hard-fenced to Standing.CANDIDATE and authorizes_actuation=False.

## Planning advice

PlanningAdvice is bound to:

- exact planning subject identity;
- exact formal FOND/HDDL projection identity;
- exact computation artifact identity;
- typed advice kind;
- scored candidate references.

order_formally_admitted() is deliberately asymmetric. Formal machinery supplies the admitted candidate set. Model advice may reorder members of that set. It may neither add a non-applicable action/method nor silently prune an admitted one.

This makes GNN/sklearn/ONNX guidance search geometry rather than planning law.

## Runtime portability

qualify_runtime_equivalence() is the narrow transport court for moving an already-qualified computation between runtimes such as PyTorch -> ONNX -> Ortex/Nx. The candidate runtime must preserve the complete output key set, bounded numeric error, and deterministic ranking.

Passing runtime equivalence does not promote semantic standing or execution authority.

## Training-data provenance

TrainingExample preserves the evidence class of every learner input. A ggen_igniter-manufactured world remains GGEN_MANUFACTURED; solver labels remain SOLVER_DERIVED; simulations remain SIMULATED; only actual admitted runtime observation may be OBSERVED_RUNTIME. Synthetic evidence therefore cannot silently acquire production standing merely because it trains a successful model.

## GALL learner ladder

GALL compares increasingly expensive implementations of the same semantic capability:

exact lookup -> nearest neighbors -> linear -> tree ensemble -> gradient boosting -> GNN -> LLM.

LearnerTier represents computational complexity, not quality. LearnerQualification binds one artifact to one exact qualification court and records utility, training cost, inference latency, and whether the formal solution was preserved.

select_least_complex_qualifying() may select a learner only when the exact court passes, the formal solution remains unchanged, and the declared utility threshold is met. A faster learner that changes formal correctness is not eligible. A GNN or LLM therefore has to earn the additional complexity rather than receiving architectural privilege.

## Intended composition

ggen_igniter may manufacture synthetic semantic worlds and solver-labeled corpora. GALL compares increasingly complex learners against cheaper baselines. The least complex implementation that closes the court may supply the capability. Repeated verified work should compile into MachineExperience/KNOWN routes so learned inference can retire for that equivalence class.

The universal invariant remains:

model output != admission != authority != DO != receipt.
