import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

await page.goto("http://127.0.0.1:8000/accounts/login/");
await page.fill('input[name="username"]', "doctor1");
await page.fill('input[name="password"]', "Doctor1234!");
await page.click('button[type="submit"]');
await page.waitForLoadState("networkidle");
await page.waitForTimeout(1000);
console.log("URL after login:", page.url());
await page.screenshot({ path: "._dashboard-screenshot.png", fullPage: true });
await browser.close();
