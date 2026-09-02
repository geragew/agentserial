import { spawn } from "node:child_process";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";


const root = path.resolve(import.meta.dirname, "..");
const python = process.env.PYTHON || "python";
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const server = spawn(python, ["-m", "uvicorn", "agentserial.api:app", "--host", "127.0.0.1", "--port", "8766"], {
  cwd: root,
  stdio: "ignore",
});

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch("http://127.0.0.1:8766/health");
      if (response.ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error("API server did not become ready");
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ executablePath: edge, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(`${pathToFileURL(path.join(root, "index.html")).href}#workspace`);
  await page.click("#openAnalyzer");
  await page.fill("#apiEndpoint", "http://127.0.0.1:8766");
  await page.setInputFiles("#historyFile", path.join(root, "examples", "06_schedule_dependent", "history.json"));
  await page.setInputFiles("#contractFile", path.join(root, "examples", "06_schedule_dependent", "contract.yaml"));
  await page.click("#submitAnalysis");
  await page.locator("#analyzerResult:not([hidden])").waitFor();
  const verdict = await page.locator("#apiVerdict").innerText();
  if (verdict !== "SCHEDULE_DEPENDENT") throw new Error(`unexpected API verdict: ${verdict}`);
  console.log("UI + API file analysis: PASS");
} finally {
  if (browser) await browser.close();
  server.kill();
}
