import { TriageResponseSchema } from "../lib/contracts/wd-fa.js";

const known = TriageResponseSchema.parse({
  case_id: "KNOWN-A",
  standing: "ALIVE",
  admitted_mode: "MODE-A-FIRMWARE",
  next_action: "run_firmware_regression",
  authority: "SELECT_ONLY",
});

const novel = TriageResponseSchema.parse({
  case_id: "NOVEL-X",
  standing: "UNKNOWN",
  admitted_mode: null,
  next_action: "open_novel_failure_investigation",
  authority: "SELECT_ONLY",
});

if (known.standing !== "ALIVE" || novel.standing !== "UNKNOWN") process.exit(2);
console.log("WD_FA_WEB_CONTRACT_ALIVE");
