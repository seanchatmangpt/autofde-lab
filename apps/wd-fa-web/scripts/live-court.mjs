import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });

  await page.selectOption("#case", { label: "known_a" });
  await page.getByRole("button", { name: "Run bounded triage" }).click();
  await page.getByText("MODE-A-FIRMWARE", { exact: false }).first().waitFor();
  const known = await page.locator(".result").innerText();
  if (!known.includes("ALIVE") || !known.includes("SELECT_ONLY")) process.exit(21);
  if (!known.includes("ENGINEER_DISPOSITION_REQUIRED")) process.exit(24);
  if (!known.includes("SYNTH-FA-A-001")) process.exit(25);
  if (!known.includes("fixture://fa-report/KNOWN-A#waveform")) process.exit(26);

  await page.selectOption("#case", { label: "novel_x" });
  await page.getByRole("button", { name: "Run bounded triage" }).click();
  await page.getByText("open_novel_failure_investigation").waitFor();
  const novel = await page.locator(".result").innerText();
  if (!novel.includes("UNKNOWN") || !novel.includes("SELECT_ONLY")) process.exit(22);
  if (!novel.includes("NO_RULE_ADMISSION_CANDIDATE_RANKING_NON_AUTHORITATIVE")) process.exit(27);
  if (!novel.includes("ESCALATE")) process.exit(28);

  const health = await page.evaluate(async () => {
    const response = await fetch("http://127.0.0.1:8000/health");
    return { status: response.status, body: await response.json() };
  });
  if (health.status !== 200 || health.body.authority !== "NO_DO") process.exit(23);

  console.log("WD_FA_GROUNDED_SERVED_BROWSER_TRANSPORT_ALIVE");
} finally {
  await browser.close();
}
