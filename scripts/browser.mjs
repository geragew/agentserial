import { existsSync } from "node:fs";
import { chromium } from "playwright";


const windowsEdge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

export function launchBrowser() {
  const options = { headless: true };
  if (process.platform === "win32" && existsSync(windowsEdge)) options.executablePath = windowsEdge;
  return chromium.launch(options);
}
