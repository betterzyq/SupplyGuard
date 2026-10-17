/** P4 business prediction and admin contract review; no external resources. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(
  root,
  process.env.SUPPLYGUARD_BROWSER_OUTPUT || ".local/acceptance/phase-4",
);
await fs.mkdir(output, { recursive: true });
const { chromium } = await import(
  path.join(root, ".local/browser-qa/node_modules/playwright/index.mjs")
);
const checks = [],
  errors = [],
  external = [];
const check = (ok, label) => {
  assert.ok(ok, label);
  checks.push(label);
  console.log("PASS " + label);
};
let browser;
try {
  browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--use-angle=swiftshader",
      "--renderer-process-limit=2",
      "--js-flags=--max-old-space-size=512",
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    recordVideo: {
      dir: path.join(output, "video"),
      size: { width: 1366, height: 768 },
    },
    acceptDownloads: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !r.url().startsWith("http://127.0.0.1:3100/")
    )
      external.push(r.url());
  });
  const login = async (role) => {
    await page.goto("http://127.0.0.1:3100/login");
    await page.getByLabel("邮箱", { exact: true }).fill(role + "@example.com");
    await page
      .getByLabel("密码", { exact: true })
      .fill(process.env.SUPPLYGUARD_DEMO_PASSWORD || "password123");
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await page.getByTestId("exposure-value").waitFor();
  };
  await login("enterprise");
  await page.getByRole("link", { name: "预测验证", exact: true }).click();
  await page.getByTestId("prediction-page").waitFor();
  check(
    await page.getByText("制造业迁移尚未验证", { exact: true }).isVisible(),
    "retail domain and manufacturing limitation visible",
  );
  check(
    (await page.getByTestId("test-ap").textContent()).includes("85.8"),
    "locked test AP rendered",
  );
  check(
    await page
      .getByRole("cell", { name: "按订单金额排序", exact: true })
      .isVisible(),
    "amount ranking baseline visible",
  );
  check(
    await page
      .getByRole("cell", { name: "固定发运规则", exact: true })
      .isVisible(),
    "strong business rule baseline visible",
  );
  check(
    await page.getByRole("img", { name: /测试集概率校准/ }).isVisible(),
    "calibration chart rendered",
  );
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "1366 viewport has no page overflow",
  );
  await page.screenshot({
    path: path.join(output, "prediction-1366.png"),
    fullPage: true,
  });
  const calibration = page
    .getByRole("heading", { name: "概率是否可信", exact: true })
    .locator("..");
  check(
    (await calibration.textContent()).includes("5,140"),
    "frozen threshold false-positive workload is visible",
  );
  await calibration.screenshot({
    path: path.join(output, "calibration-workload-1366.png"),
  });
  const comparison = page
    .getByRole("heading", { name: "同一测试集上的模型与业务基线", exact: true })
    .locator("..");
  check(
    (await comparison.textContent()).includes("22.4%") &&
      (await comparison.textContent()).includes("29.7%"),
    "amount capture trade-off is explicit rather than claimed ROI",
  );
  await comparison.screenshot({
    path: path.join(output, "baseline-comparison-1366.png"),
  });
  await page.getByLabel("分组维度").selectOption("market");
  check(
    await page.getByText("Pacific Asia", { exact: true }).isVisible(),
    "market subgroup updates",
  );
  const selector = page.getByLabel("历史订单样例");
  await selector.locator("option").nth(1).waitFor({ state: "attached" });
  const value = await selector.locator("option").nth(1).getAttribute("value");
  await selector.selectOption(value);
  await page
    .getByRole("button", { name: "运行历史样例预测", exact: true })
    .click();
  await page.getByTestId("prediction-result").waitFor();
  check(
    (await page.getByTestId("prediction-result").textContent()).includes(
      "实际结果",
    ),
    "trained inference result and outcome available for review",
  );
  await page
    .getByTestId("prediction-result")
    .screenshot({ path: path.join(output, "historical-prediction-1366.png") });
  await selector.selectOption("");
  check(
    (await page.getByTestId("prediction-result").count()) === 0,
    "changing case clears previous probability",
  );
  check(
    await page
      .getByRole("button", { name: "运行历史样例预测", exact: true })
      .isDisabled(),
    "empty case cannot score",
  );
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "完整评测 JSON", exact: true })
    .click();
  const download = await downloadPromise;
  const target = path.join(output, "downloaded-report.json");
  await download.saveAs(target);
  const report = JSON.parse(await fs.readFile(target, "utf8"));
  check(
    report.domain === "dataco-retail-historical" &&
      report.models[report.selection.name].test.count === 13071,
    "download contains real locked experiment, not UI-only values",
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({
    path: path.join(output, "prediction-1920.png"),
    fullPage: true,
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "1920 viewport has no page overflow",
  );
  await page.goto("http://127.0.0.1:3100/benchmarks");
  await page.getByRole("heading", { name: "此页面仅供管理员使用" }).waitFor();
  check(true, "enterprise blocked from admin evaluation UI");
  await page.getByRole("button", { name: "返回经营总览" }).click();
  await page.getByTestId("exposure-value").waitFor();
  await page.getByRole("button", { name: "退出登录" }).click();
  await login("admin");
  await page.goto("http://127.0.0.1:3100/benchmarks");
  await page.getByTestId("evaluation-contracts").waitFor();
  check(
    await page.getByText("17 项 · 全部通过", { exact: true }).isVisible(),
    "admin sees 17 offline contracts separately",
  );
  check(
    await page.getByText("未实测，不报告准确率", { exact: true }).isVisible(),
    "offline contract result not presented as live retrieval accuracy",
  );
  await page.getByText("查看逐项检查与待实测金标准", { exact: true }).click();
  check(
    await page.getByText("path-reversed", { exact: true }).isVisible(),
    "directional path scorer audit visible",
  );
  await page.screenshot({
    path: path.join(output, "evaluation-contracts-1920.png"),
    fullPage: true,
  });
  await page.goto("http://127.0.0.1:3100/prediction");
  await page.getByTestId("prediction-page").waitFor();
  check(true, "admin can also review business prediction");
  check(errors.length === 0, "no uncaught browser errors");
  check(external.length === 0, "no third-party runtime resources");
  await context.close();
  await fs.writeFile(
    path.join(output, "browser.json"),
    JSON.stringify(
      {
        status: "passed",
        checked_at: new Date().toISOString(),
        checks,
        errors,
        external,
      },
      null,
      2,
    ) + "\n",
  );
} catch (e) {
  await fs.writeFile(
    path.join(output, "browser-failure.json"),
    JSON.stringify(
      { status: "failed", checks, errors, external, error: String(e) },
      null,
      2,
    ),
  );
  throw e;
} finally {
  await browser?.close();
}
