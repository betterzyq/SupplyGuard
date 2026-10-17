/** Optional Chromium acceptance; tooling and runtime stay inside .local/. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(
  root,
  process.env.SUPPLYGUARD_BROWSER_OUTPUT || ".local/acceptance/phase-1",
);
const { chromium } = await import(
  path.join(root, ".local/browser-qa/node_modules/playwright/index.mjs")
);
await fs.mkdir(output, { recursive: true });
const errors = [];
const checks = [];
let browser;
function check(condition, label) {
  assert.ok(condition, label);
  checks.push(label);
  console.log(`PASS ${label}`);
}
try {
  browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--renderer-process-limit=2",
      "--js-flags=--max-old-space-size=512",
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  page.setDefaultTimeout(15000);
  const heading = (name) => page.getByRole("heading", { name, exact: true });
  const waitOverview = () => page.getByTestId("exposure-value").waitFor();
  await page.goto("http://127.0.0.1:3100/login");
  check(
    (await page
      .getByRole("button", { name: "企业用户", exact: true })
      .count()) === 1,
    "enterprise quick login visible",
  );
  check(
    (await page
      .getByRole("button", { name: "管理员（开发人员）", exact: true })
      .count()) === 1,
    "admin quick login visible",
  );
  await page.screenshot({
    path: path.join(output, "login-1366.png"),
    fullPage: true,
  });
  await page.getByLabel("邮箱", { exact: true }).fill("enterprise@example.com");
  await page
    .getByLabel("密码", { exact: true })
    .fill(process.env.SUPPLYGUARD_DEMO_PASSWORD || "password123");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await waitOverview();
  check(
    await heading("经营总览").isVisible(),
    "enterprise business overview rendered",
  );
  check(
    /3,380,000/.test(await page.getByTestId("exposure-value").innerText()),
    "port exposure reconciles in browser",
  );
  check(
    (await page
      .getByRole("link", { name: "基准评测", exact: true })
      .count()) === 0,
    "enterprise has no developer navigation",
  );
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    "1366px page has no horizontal overflow",
  );
  await page.screenshot({
    path: path.join(output, "overview-1366.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "二级供应商停产", exact: true })
    .click();
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="exposure-value"]')
      ?.textContent.includes("3,860,000"),
  );
  check(true, "tier2 scenario changes overview amount");
  await page.getByRole("link", { name: "风险研判", exact: true }).click();
  await heading("风险研判").waitFor();
  await page.getByText("二级连接器供应站点停产", { exact: true }).waitFor();
  check(true, "scenario retained across business pages");
  await page.getByRole("button", { name: "区域灾害", exact: true }).click();
  await page.getByText("区域强降雨影响材料运输", { exact: true }).waitFor();
  await page.getByRole("link", { name: "经营总览", exact: true }).click();
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="exposure-value"]')
      ?.textContent.includes("1,780,000"),
  );
  check(true, "regional scenario consistent with overview");
  await page
    .getByText("数据来源与指标口径（可人工核算）", { exact: true })
    .click();
  check(
    await page.getByText(/首页处置状态为固定演示记录.*持久化任务/).isVisible(),
    "metric limitations visible",
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    "1920px page has no horizontal overflow",
  );
  await page.screenshot({
    path: path.join(output, "overview-1920.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "企业知识库", exact: true }).click();
  await heading("企业知识库").waitFor();
  check(
    await page.getByText(/上传内容在本企业内共享/).isVisible(),
    "documents explain enterprise sharing",
  );
  for (const route of ["benchmarks", "audit", "settings"]) {
    await page.goto(`http://127.0.0.1:3100/${route}`);
    await heading("此页面仅供管理员使用").waitFor();
    check(true, `enterprise direct /${route} blocked before content`);
  }
  await page.getByRole("button", { name: "返回经营总览", exact: true }).click();
  await waitOverview();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await heading("登录").waitFor();
  await page.getByLabel("邮箱", { exact: true }).fill("admin@example.com");
  await page
    .getByLabel("密码", { exact: true })
    .fill(process.env.SUPPLYGUARD_DEMO_PASSWORD || "password123");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await waitOverview();
  check(
    await page.getByText("开发与运维", { exact: true }).isVisible(),
    "admin developer section visible after account switch",
  );
  await page.getByText("开发与运维", { exact: true }).click();
  await page.getByRole("link", { name: "基准评测", exact: true }).click();
  await heading("基准评测实验").waitFor();
  check(
    await page.getByText(/历史岗位权限基准不适用于 enterprise-v2/).isVisible(),
    "admin sees legacy benchmark limitation",
  );
  await page.screenshot({
    path: path.join(output, "admin-benchmarks-1920.png"),
    fullPage: true,
  });
  check(errors.length === 0, "no unhandled browser errors");
  await fs.writeFile(
    path.join(output, "browser.json"),
    JSON.stringify(
      {
        status: "passed",
        checked_at: new Date().toISOString(),
        checks,
        errors,
      },
      null,
      2,
    ),
  );
  await context.close();
} catch (error) {
  await fs.writeFile(
    path.join(output, "browser.json"),
    JSON.stringify(
      { status: "failed", checks, errors, failure: error.message },
      null,
      2,
    ),
  );
  throw error;
} finally {
  await browser?.close();
}
