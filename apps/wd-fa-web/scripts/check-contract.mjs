import { TriageResponseSchema } from "../lib/contracts/wd-fa.js";

const evidence = [
  {
    evidence_id: "KNOWN-A:test",
    kind: "test",
    modality: "structured_test_result",
    source_ref: "fixture://datalake/test-results/KNOWN-A",
    digest: "sha256:" + "0".repeat(64),
  },
];

const hypothesis = {
  mode_id: "MODE-A-FIRMWARE",
  candidate_score: 1,
  score_basis: "STRUCTURAL_SIMILARITY",
  structural_similarity: 1,
  deterministic_match: true,
  evidence_completeness: 1,
  prior_case_ids: ["SYNTH-FA-A-001"],
  evidence_ids: ["KNOWN-A:test"],
  owning_team: "firmware_analysis",
  action_type: "TEST",
  next_action: "run_firmware_regression",
};

const known = TriageResponseSchema.parse({
  case_id: "KNOWN-A",
  standing: "ALIVE",
  admitted_mode: "MODE-A-FIRMWARE",
  ranked_hypotheses: [hypothesis],
  closest_prior_cases: ["SYNTH-FA-A-001"],
  supporting_evidence: evidence,
  next_action: "run_firmware_regression",
  action_type: "TEST",
  owning_team: "firmware_analysis",
  evidence_completeness: 1,
  confidence_basis: "DETERMINISTIC_RULE_AND_REQUIRED_EVIDENCE",
  human_gate: "ENGINEER_DISPOSITION_REQUIRED",
  trace_id: "sha256:" + "1".repeat(64),
  authority: "SELECT_ONLY",
});

const novel = TriageResponseSchema.parse({
  case_id: "NOVEL-X",
  standing: "UNKNOWN",
  admitted_mode: null,
  ranked_hypotheses: [{ ...hypothesis, deterministic_match: false }],
  closest_prior_cases: ["SYNTH-FA-A-001"],
  supporting_evidence: evidence,
  next_action: "open_novel_failure_investigation",
  action_type: "ESCALATE",
  owning_team: "failure_analysis",
  evidence_completeness: 0,
  confidence_basis: "NO_RULE_ADMISSION_CANDIDATE_RANKING_NON_AUTHORITATIVE",
  human_gate: "ENGINEER_DISPOSITION_REQUIRED",
  trace_id: "sha256:" + "2".repeat(64),
  authority: "SELECT_ONLY",
});

if (known.standing !== "ALIVE" || novel.standing !== "UNKNOWN") process.exit(2);
if (known.human_gate !== "ENGINEER_DISPOSITION_REQUIRED") process.exit(3);
console.log("WD_FA_WEB_CONTRACT_ALIVE");
