import { z } from "zod";

/**
 * @typedef {Object} TriageResponse
 * @property {string} case_id
 * @property {"UNKNOWN"|"PARTIAL_ALIVE"|"ALIVE"|"BLOCKED"|"REFUSED"} standing
 * @property {string|null} admitted_mode
 * @property {string} next_action
 * @property {"SELECT_ONLY"} authority
 */
export const TriageResponseSchema = z.object({
  case_id: z.string().min(1),
  standing: z.enum(["UNKNOWN", "PARTIAL_ALIVE", "ALIVE", "BLOCKED", "REFUSED"]),
  admitted_mode: z.string().nullable(),
  next_action: z.string().min(1),
  authority: z.literal("SELECT_ONLY"),
});
