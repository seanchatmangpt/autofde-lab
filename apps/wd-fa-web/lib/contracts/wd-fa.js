import { z } from "zod";

// UNSUPPORTED(generator-capability:collection-valued-projection):
// the marketplace generator owns the scalar SHACL envelope; these collection-valued
// evidence/ranking extensions remain explicit adapter residue until that pack can project them.
export const HypothesisResponseSchema = z.object({
  mode_id: z.string().min(1),
  candidate_score: z.number(),
  score_basis: z.enum(["TPOT_CANDIDATE_SCORE", "STRUCTURAL_SIMILARITY"]),
  structural_similarity: z.number().min(0).max(1),
  deterministic_match: z.boolean(),
  evidence_completeness: z.number().min(0).max(1),
  prior_case_ids: z.array(z.string().min(1)),
  evidence_ids: z.array(z.string().min(1)),
  owning_team: z.string().min(1),
  action_type: z.string().min(1),
  next_action: z.string().min(1),
});

export const EvidenceReferenceSchema = z.object({
  evidence_id: z.string().min(1),
  kind: z.string().min(1),
  modality: z.string().min(1),
  source_ref: z.string().min(1),
  digest: z.string().startsWith("sha256:"),
});

/**
 * @typedef {Object} TriageResponse
 * @property {string} case_id
 * @property {"UNKNOWN"|"PARTIAL_ALIVE"|"ALIVE"|"BLOCKED"|"REFUSED"} standing
 * @property {string|null} admitted_mode
 * @property {Array<Object>} ranked_hypotheses
 * @property {Array<string>} closest_prior_cases
 * @property {Array<Object>} supporting_evidence
 * @property {string} next_action
 * @property {string} action_type
 * @property {string} owning_team
 * @property {number} evidence_completeness
 * @property {string} confidence_basis
 * @property {"ENGINEER_DISPOSITION_REQUIRED"} human_gate
 * @property {string} trace_id
 * @property {"SELECT_ONLY"} authority
 */
export const TriageResponseSchema = z.object({
  case_id: z.string().min(1),
  standing: z.enum(["UNKNOWN", "PARTIAL_ALIVE", "ALIVE", "BLOCKED", "REFUSED"]),
  admitted_mode: z.string().nullable(),
  ranked_hypotheses: z.array(HypothesisResponseSchema).min(1),
  closest_prior_cases: z.array(z.string().min(1)),
  supporting_evidence: z.array(EvidenceReferenceSchema).min(1),
  next_action: z.string().min(1),
  action_type: z.string().min(1),
  owning_team: z.string().min(1),
  evidence_completeness: z.number().min(0).max(1),
  confidence_basis: z.string().min(1),
  human_gate: z.literal("ENGINEER_DISPOSITION_REQUIRED"),
  trace_id: z.string().startsWith("sha256:"),
  authority: z.literal("SELECT_ONLY"),
});
