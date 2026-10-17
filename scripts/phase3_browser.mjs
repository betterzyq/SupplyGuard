/** P3 business flows, independently checked arithmetic and saved snapshots. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(
  root,
  process.env.SUPPLYGUARD_BROWSER_OUTPUT || ".local/acceptance/phase-3",
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
  console.log(`PASS ${label}`);
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
  page.setDefaultTimeout(25000);
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !r.url().startsWith("http://127.0.0.1:3100/")
    )
      external.push(r.url());
  });
  await page.goto("http://127.0.0.1:3100/login");
  await page.getByLabel("邮箱", { exact: true }).fill("enterprise@example.com");
  await page
    .getByLabel("密码", { exact: true })
    .fill(process.env.SUPPLYGUARD_DEMO_PASSWORD || "password123");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByTestId("exposure-value").waitFor();
  await page.getByRole("link", { name: "风险控制塔", exact: true }).click();
  await page.locator('[data-map-ready="true"]').waitFor({ timeout: 45000 });
  await page.getByRole("button", { name: /宁波港集装箱作业拥堵/ }).click();
  await page
    .getByTestId("network-detail")
    .getByRole("link", { name: "模拟影响与方案", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "影响模拟与方案比较", exact: true })
    .waitFor();
  await page.getByLabel("MAT-01初始库存", { exact: true }).waitFor();
  check(
    (await page.getByLabel("模拟事件", { exact: true }).inputValue()) ===
      "EVT-PORT",
    "map event opens matching simulation scenario and event",
  );
  await page.screenshot({
    path: path.join(output, "simulation-inputs-1366.png"),
    fullPage: true,
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "1366px simulation has no page overflow",
  );
  await page.getByLabel("输入样例", { exact: true }).selectOption("hand-check");
  await page.waitForFunction(
    () =>
      document.querySelector('[aria-label="MAT-01常规日到货"]')?.value === "20",
  );
  check(
    (await page.getByLabel("方案 A措施1数量", { exact: true }).inputValue()) ===
      "20",
    "hand fixture sets inventory 100, demand 20 and feasible alternative quantity",
  );
  const run = async () => {
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/simulation/comparison") &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "运行影响模拟并比较方案", exact: true })
      .click();
    const response = await pending;
    assert.equal(response.status(), 200, await response.text());
    const data = await response.json();
    await page.getByTestId("simulation-results").waitFor();
    await page.waitForFunction(
      (id) => document.body.textContent.includes(id),
      data.comparison_id,
    );
    return data;
  };
  await page.getByLabel("停供 / 受扰天数", { exact: true }).fill("3");
  let data = await run();
  check(
    data.baseline.result.metrics.delayed_orders === 0 &&
      data.baseline.result.materials[0].peak_shortage_units === "0",
    "hand case: 3-day interruption has no shortage or delayed order",
  );
  await page.getByLabel("停供 / 受扰天数", { exact: true }).fill("7");
  check(
    await page
      .getByRole("status")
      .filter({ hasText: "参数已修改" })
      .isVisible(),
    "modified inputs mark saved result stale before rerun",
  );
  data = await run();
  check(
    data.baseline.result.metrics.first_shortage_day === 5 &&
      data.baseline.result.materials[0].peak_shortage_units === "40",
    "hand case: 7-day interruption first shortage D6, peak 40",
  );
  check(
    data.plans.every((p) => p.run.result.metrics.delayed_orders === 0),
    "effective alternative and transfer both protect the hand-case order",
  );
  check(
    data.plans[0].delta.incremental_cost_cny === "4500.00" &&
      data.plans[1].delta.incremental_cost_cny === "1140.00",
    "cost ledgers match independent 4500 / 1140 arithmetic",
  );
  check(
    /1,280,000/.test(
      await page.getByTestId("simulation-baseline-amount").innerText(),
    ),
    "browser baseline amount matches API unique order amount",
  );
  await page.getByRole("button", { name: "D6", exact: true }).click();
  check(
    await page.getByText("净缺口 20", { exact: true }).isVisible(),
    "interactive daily stock view shows D6 net material shortage 20",
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page
    .getByTestId("simulation-baseline")
    .locator("..")
    .screenshot({ path: path.join(output, "comparison-cards-1920.png") });
  await page
    .getByRole("img", { name: /各方案每日结余库存折线图/ })
    .locator("..")
    .screenshot({ path: path.join(output, "stock-timeline-1920.png") });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "1920px comparison no page overflow",
  );
  await page.getByLabel("MAT-01初始库存", { exact: true }).fill("200");
  data = await run();
  check(
    data.baseline.result.metrics.first_shortage_day === null,
    "increased inventory removes shortage without changing event",
  );
  await page.getByLabel("需求规模 %", { exact: true }).fill("0");
  data = await run();
  check(
    data.baseline.result.metrics.delayed_orders === 0 &&
      data.baseline.result.materials[0].initial_buffer_days === null,
    "zero demand gives no shortage and N/A buffer, not infinity",
  );
  await page.getByLabel("需求规模 %", { exact: true }).fill("100");
  await page.getByLabel("MAT-01初始库存", { exact: true }).fill("100");
  const planA = page
    .getByRole("heading", { name: "方案 A", exact: true })
    .locator("..");
  await planA
    .getByRole("button", { name: "+ 添加组合措施", exact: true })
    .click();
  data = await run();
  check(
    data.plans[0].run.result.metrics.incremental_cost_cny === "5640.00",
    "combined measures sum exact costs once: 4500 + 1140",
  );
  const uncertified = page
    .getByLabel("方案 A措施1", { exact: true })
    .getByRole("option", { name: /未认证/ });
  check(
    await uncertified.first().evaluate((option) => option.disabled),
    "uncertified alternatives visibly disabled",
  );
  await page
    .getByLabel("输入样例", { exact: true })
    .selectOption("manufacturing");
  await page.getByLabel("MAT-03初始库存", { exact: true }).waitFor();
  await page
    .getByLabel("方案 A措施1", { exact: true })
    .selectOption("reroute-MAT-01");
  await page
    .getByLabel("方案 B措施1", { exact: true })
    .selectOption("expedite-MAT-01");
  data = await run();
  const mat = data.plans[0].run.result.materials.find((m) => m.id === "MAT-01");
  check(
    mat.daily.reduce((sum, d) => sum + Number(d.inbound_receipts), 0) === 80 &&
      data.plans[0].delta.incremental_cost_cny === "2800.00",
    "reroute reschedules the existing 80-unit lot once and costs 2800",
  );
  check(
    data.plans[1].delta.incremental_cost_cny === "2000.00" &&
      data.plans[1].run.result.metrics.delayed_order_amount_cny ===
        data.baseline.result.metrics.delayed_order_amount_cny,
    "ineffective expedite remains charged and does not invent improvement",
  );
  for (const scene of ["tier2-shutdown", "regional-flood"]) {
    await page.getByLabel("仿真场景", { exact: true }).selectOption(scene);
    await page.waitForFunction(
      (target) => document.querySelector("select")?.value === target,
      scene,
    );
    data = await run();
    check(
      data.baseline.input_snapshot.config.scenario_id === scene,
      `new scenario clears old plan and computes ${scene}`,
    );
  }
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "下载输入与结果 JSON", exact: true })
    .click();
  const download = await downloadPromise;
  const downloadPath = path.join(output, "downloaded-snapshot.json");
  await download.saveAs(downloadPath);
  const snapshot = JSON.parse(await fs.readFile(downloadPath, "utf8"));
  check(
    snapshot.comparison_id === data.comparison_id &&
      snapshot.baseline.input_snapshot.config.bom,
    "download contains full versioned input and reproducible result",
  );
  const saved = await page.evaluate(async (id) => {
    const r = await fetch(`/api/v1/simulation/runs/${id}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("sg_token")}` },
    });
    return { status: r.status, data: await r.json() };
  }, data.comparison_id);
  check(
    saved.status === 200 && saved.data.comparison_id === data.comparison_id,
    "authenticated saved snapshot remains readable",
  );
  const invalid = await page.evaluate(async () => {
    const r = await fetch("/api/v1/simulation/run", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${localStorage.getItem("sg_token")}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        measures: [
          { option_id: "alternative-MAT-01-uncertified", quantity: 10 },
        ],
      }),
    });
    return r.status;
  });
  check(invalid === 422, "server independently rejects uncertified measure");
  check(
    external.length === 0,
    "no external model/map requests during simulation",
  );
  check(errors.length === 0, "no unhandled browser errors");
  await fs.writeFile(
    path.join(output, "browser.json"),
    JSON.stringify(
      {
        status: "passed",
        checked_at: new Date().toISOString(),
        checks,
        errors,
        external,
        video: path.relative(root, await page.video().path()),
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
      { status: "failed", checks, errors, external, failure: error.message },
      null,
      2,
    ),
  );
  throw error;
} finally {
  await browser?.close();
}
