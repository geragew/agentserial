import { chromium } from "playwright";
import { pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const target = pathToFileURL(path.join(root, "index.html")).href;
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch({ executablePath: edge, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto(target);
  assert(await page.locator("h1").first().innerText() === "Agentes podem acertar sozinhos\ne falhar juntos.", "home headline mismatch");
  await page.click('[data-theme-toggle]');
  assert(await page.locator("html").getAttribute("data-theme") === "dark", "dark theme did not activate");
  await page.reload();
  assert(await page.locator("html").getAttribute("data-theme") === "dark", "dark theme did not persist");
  await page.click('[data-theme-toggle]');

  await page.click('a[href="#workspace"]');
  await page.waitForTimeout(150);
  assert(await page.locator("#runTitle").innerText() === "Parallel Payment Agents", "workspace did not open");

  await page.selectOption("#exampleSelect", "booking");
  await page.click("#loadExample");
  assert(await page.locator("#runTitle").innerText() === "Concurrent Seat Reservation", "example selection failed");
  assert(await page.locator("#historyBody tr").count() === 6, "booking history row count mismatch");

  await page.click('[data-view="history"]');
  await page.selectOption("#agentFilter", "agent-a");
  const visibleRows = await page.locator("#historyBody tr:not([hidden])").count();
  assert(visibleRows === 3, "agent filter failed");
  await page.click("#historyBody tr:not([hidden])");
  assert(await page.locator("#detailDrawer").getAttribute("aria-hidden") === "false", "operation drawer did not open");
  await page.click('[data-drawer-mode="raw"]');
  assert((await page.locator("#drawerContent").innerText()).includes("RAW EVENT"), "raw event mode failed");
  await page.click("#closeDrawer");

  await page.click('[data-view="contract"]');
  await page.click('[data-code-mode="raw"]');
  assert((await page.locator("#contractCode").innerText()).startsWith('{"version"'), "raw contract mode failed");
  await page.click('[data-view="counterexample"]');
  assert(await page.locator("#counterDetail .counter-operation").count() === 4, "counterexample view mismatch");
  await page.click('[data-view="runs"]');
  assert(await page.locator("#runsBody tr").count() === 5, "runs view mismatch");
  await page.click('[data-view="specification"]');
  assert(await page.locator(".spec-layout article section").count() === 4, "specification view mismatch");

  const desktopOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  assert(!desktopOverflow, "desktop has global horizontal overflow");

  await page.setViewportSize({ width: 900, height: 1000 });
  await page.goto(`${target}#workspace/overview`);
  await page.waitForTimeout(100);
  const tabletOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  assert(!tabletOverflow, "tablet has global horizontal overflow");
  await page.click("#menuButton");
  assert(await page.locator("#sidebar").evaluate(node => node.classList.contains("open")), "tablet navigation did not open");
  assert(errors.length === 0, `browser errors:\n${errors.join("\n")}`);
  console.log("UI interactions: PASS");
  console.log("Desktop overflow: NONE");
  console.log("Tablet overflow: NONE");
} finally {
  await browser.close();
}
