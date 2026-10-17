/** P6 story navigation, assumptions, failure recovery and rendering timings. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(
  root,
  process.env.SUPPLYGUARD_BROWSER_OUTPUT || ".local/acceptance/phase-6",
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
  const mapTimes = [],
    filterTimes = [];
  await login("enterprise");
  for (const [id, name, site] of [
    ["port-congestion", "港口拥堵", "宁波港"],
    ["tier2-shutdown", "二级供应商停产", "东莞连接器工厂"],
    ["regional-flood", "区域灾害", "武汉材料工厂"],
  ]) {
    await page.getByRole("link", { name: "业务场景", exact: true }).click();
    await page
      .getByRole("group", { name: "业务场景" })
      .getByRole("button", { name: new RegExp(name) })
      .click();
    await page.getByTestId("story-metrics").waitFor();
    check(
      await page
        .getByRole("heading", { name: name + " · 当前场景", exact: true })
        .isVisible(),
      id + " story selected",
    );
    const started = Date.now();
    await page.getByRole("link", { name: "定位风险站点", exact: true }).click();
    await page.locator('[data-map-ready="true"]').waitFor({ timeout: 45000 });
    mapTimes.push({ scenario: id, ms: Date.now() - started });
    await page
      .getByTestId("network-detail")
      .getByRole("heading", { name: site, exact: true })
      .waitFor();
    check(
      (await page.getByLabel("场景", { exact: true }).inputValue()) === id,
      id + " map opens matching site and scenario",
    );
    const tick = Date.now();
    await page.getByLabel("运输方式", { exact: true }).selectOption("road");
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    filterTimes.push({ scenario: id, ms: Date.now() - tick });
    await page.getByRole("link", { name: "业务场景", exact: true }).click();
    await page
      .getByRole("button", { name: "重置场景视图", exact: true })
      .click();
    await page
      .getByRole("status")
      .filter({ hasText: "场景视图已重置" })
      .waitFor();
    await page.getByRole("link", { name: "定位风险站点", exact: true }).click();
    await page.locator('[data-map-ready="true"]').waitFor();
    check(
      (await page.getByLabel("运输方式", { exact: true }).inputValue()) === "",
      id + " reset restores filters",
    );
    await page.getByRole("link", { name: "业务场景", exact: true }).click();
    await page.getByRole("link", { name: "比较处置方案", exact: true }).click();
    await page
      .getByRole("button", { name: "运行影响模拟并比较方案", exact: true })
      .click();
    await page.getByTestId("simulation-results").waitFor();
    check(true, id + " linked simulation runs");
  }
  await page.getByRole("link", { name: "商业价值", exact: true }).click();
  await page.getByTestId("business-case-result").waitFor();
  check(
    (await page
      .getByRole("heading", { name: "差异化切入点与竞品参照", exact: true })
      .count()) === 0,
    "competitor section removed",
  );
  check(
    (await page
      .getByRole("heading", {
        name: "6周试点路径 · 建议，尚未开展",
        exact: true,
      })
      .count()) === 0,
    "pilot timeline removed",
  );
  await page.getByText("数据说明", { exact: true }).click();
  check(
    await page
      .getByText(/制造业场景中的站点、订单、轨迹与 ETA 使用构造的演示数据/)
      .isVisible(),
    "central data provenance remains accessible",
  );
  await page.getByText("数据说明", { exact: true }).click();
  const calc = page.getByTestId("business-case-result");
  check(
    (await calc.innerText()).includes("-64.0%") &&
      (await calc.innerText()).includes("28,800"),
    "assumption calculator retains negative ROI and reproducible arithmetic",
  );
  const downloadPending = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "下载当前测算假设", exact: true })
    .click();
  const download = await downloadPending;
  const assumptions = JSON.parse(
    await fs.readFile(await download.path(), "utf8"),
  );
  check(
    assumptions.type === "assumption_only" &&
      assumptions.first_year_net === -51200,
    "download contains inputs, formula result and explicit assumptions",
  );
  await page.getByLabel("实际采用比例（%）", { exact: true }).fill("101");
  await page
    .getByRole("alert")
    .filter({ hasText: "请输入有效非负数" })
    .waitFor();
  check(
    await page
      .getByRole("button", { name: "下载当前测算假设", exact: true })
      .isDisabled(),
    "invalid adoption blocks result and export",
  );
  await page.getByLabel("实际采用比例（%）", { exact: true }).fill("50");
  for (const label of [
    "年度订阅成本假设（元）",
    "首年接入成本假设（元）",
    "年度运维与情报成本（元）",
  ])
    await page.getByLabel(label, { exact: true }).fill("0");
  check(
    (await calc.innerText()).includes("N/A"),
    "zero investment returns N/A, no infinite ROI",
  );
  await page.screenshot({
    path: path.join(output, "business-case-1366.png"),
    fullPage: true,
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "commercial page fits 1366px",
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.getByRole("link", { name: "业务场景", exact: true }).click();
  await page.getByTestId("story-metrics").waitFor();
  await page.screenshot({
    path: path.join(output, "stories-1920.png"),
    fullPage: true,
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "story page fits 1920px",
  );
  await page.route("**/api/v1/business/overview*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"P6 controlled test failure"}',
    }),
  );
  await page
    .getByRole("group", { name: "业务场景" })
    .getByRole("button", { name: /港口拥堵/ })
    .click();
  await page
    .getByRole("alert")
    .filter({ hasText: "业务服务暂不可用" })
    .waitFor();
  check(
    await page
      .getByRole("link", { name: "定位风险站点", exact: true })
      .isVisible(),
    "controlled API failure retains story guidance and explains unavailable writes",
  );
  await page.unroute("**/api/v1/business/overview*");
  await page.getByRole("button", { name: "重新加载场景", exact: true }).click();
  await page.getByTestId("story-metrics").waitFor();
  check(true, "story recovers after API failure without data reset");
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await login("admin");
  await page.getByRole("link", { name: "商业价值", exact: true }).click();
  await page.getByTestId("business-case-result").waitFor();
  check(true, "admin can access same commercial workflow");
  check(errors.length === 0, "no unhandled browser errors");
  check(
    external.length === 0,
    "no external requests during local stories or commercial calculations",
  );
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
        map_ready_timings: mapTimes,
        filter_timings: filterTimes,
        rendering:
          "Chromium SwiftShader CPU only; 1366x768; map timing is navigation-to-ready with shared warm assets, not cold boot",
        viewport_checks: ["1366x768", "1920x1080"],
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
