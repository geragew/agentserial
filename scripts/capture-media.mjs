import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const media = path.join(root, "media");
const target = pathToFileURL(path.join(root, "index.html")).href;

await mkdir(media, { recursive: true });

async function verifyPage(page) {
  const failures = [];
  page.on("pageerror", error => failures.push(`pageerror: ${error.message}`));
  page.on("console", message => {
    if (message.type() === "error") failures.push(`console: ${message.text()}`);
  });
  await page.goto(target, { waitUntil: "load" });
  await page.waitForTimeout(250);
  return () => {
    if (failures.length) throw new Error(failures.join("\n"));
  };
}

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const desktopHealthy = await verifyPage(desktop);
  await desktop.screenshot({ path: path.join(media, "home-desktop.png"), fullPage: true });
  await desktop.goto(`${target}#workspace/overview`);
  await desktop.waitForTimeout(300);
  await desktop.screenshot({ path: path.join(media, "workspace-overview.png"), fullPage: true });
  await desktop.click("#openAnalyzer");
  await desktop.waitForTimeout(180);
  await desktop.screenshot({ path: path.join(media, "analyze-files.png") });
  await desktop.click("#closeAnalyzer");
  await desktop.click('[data-view="history"]');
  await desktop.click('#historyBody tr:nth-child(3)');
  await desktop.waitForTimeout(180);
  await desktop.screenshot({ path: path.join(media, "workspace-history-inspector.png"), fullPage: true });
  desktopHealthy();
  await desktop.close();

  const tablet = await browser.newPage({ viewport: { width: 900, height: 1100 }, deviceScaleFactor: 1 });
  const tabletHealthy = await verifyPage(tablet);
  await tablet.goto(`${target}#workspace/overview`);
  await tablet.waitForTimeout(250);
  await tablet.screenshot({ path: path.join(media, "workspace-tablet.png"), fullPage: true });
  tabletHealthy();
  await tablet.close();

  const userViewport = await browser.newPage({ viewport: { width: 1365, height: 768 }, deviceScaleFactor: 1 });
  const userViewportHealthy = await verifyPage(userViewport);
  await userViewport.goto(`${target}#workspace/overview`);
  await userViewport.waitForTimeout(250);
  await userViewport.screenshot({ path: path.join(media, "workspace-1365x768.png"), fullPage: true });
  userViewportHealthy();
  await userViewport.close();

  const social = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 1 });
  const socialHealthy = await verifyPage(social);
  await social.screenshot({ path: path.join(media, "social-preview.png") });
  socialHealthy();
  await social.close();

  const dark = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const darkHealthy = await verifyPage(dark);
  await dark.evaluate(() => localStorage.setItem("agentserial-theme", "dark"));
  await dark.reload();
  await dark.screenshot({ path: path.join(media, "home-dark.png"), fullPage: true });
  await dark.goto(`${target}#workspace/overview`);
  await dark.waitForTimeout(250);
  await dark.screenshot({ path: path.join(media, "workspace-dark.png"), fullPage: true });
  darkHealthy();
  await dark.close();

  const report = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  await report.goto(pathToFileURL(path.join(media, "overspend-report.html")).href, { waitUntil: "load" });
  await report.screenshot({ path: path.join(media, "report-real-history.png"), fullPage: true });
  await report.close();
} finally {
  await browser.close();
}

const videoContext = await chromium.launchPersistentContext("", {
  headless: true,
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: media, size: { width: 1280, height: 720 } }
});
let videoPath;
try {
  const page = videoContext.pages()[0];
  const healthy = await verifyPage(page);
  const video = page.video();
  await page.waitForTimeout(1600);
  await page.click('a[href="#workspace"]');
  await page.waitForTimeout(1700);
  await page.click('[data-view="history"]');
  await page.waitForTimeout(1100);
  await page.click('#historyBody tr:nth-child(3)');
  await page.waitForTimeout(1500);
  await page.click('#closeDrawer');
  await page.click('[data-view="overview"]');
  await page.selectOption("#exampleSelect", "booking");
  await page.click("#loadExample");
  await page.waitForTimeout(1100);
  await page.click("#runCheck");
  await page.waitForTimeout(1700);
  await page.click("#openAnalyzer");
  await page.waitForTimeout(1500);
  await page.click("#closeAnalyzer");
  healthy();
  videoPath = await video.path();
  await page.close();
} finally {
  await videoContext.close();
}

const { copyFile, unlink } = await import("node:fs/promises");
const finalVideo = path.join(media, "agentserial-demo.webm");
await copyFile(videoPath, finalVideo);
if (path.resolve(videoPath) !== path.resolve(finalVideo)) await unlink(videoPath);

console.log("Captured:");
console.log("  media/home-desktop.png");
console.log("  media/workspace-overview.png");
console.log("  media/analyze-files.png");
console.log("  media/workspace-history-inspector.png");
console.log("  media/workspace-tablet.png");
console.log("  media/workspace-1365x768.png");
console.log("  media/social-preview.png");
console.log("  media/home-dark.png");
console.log("  media/workspace-dark.png");
console.log("  media/report-real-history.png");
console.log("  media/agentserial-demo.webm");
