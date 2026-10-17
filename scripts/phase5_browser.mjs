/** P5 real browser workflow; no external messages or business execution. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(root, process.env.SUPPLYGUARD_BROWSER_OUTPUT || ".local/acceptance/phase-5");
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
  await page.getByRole("link", { name: "风险研判", exact: true }).click();
  await page
    .getByRole("link", { name: "建立处置任务", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "保存模拟事件，准备建任务", exact: true })
    .click();
  await page
    .getByText("演示场景已持久化，来源明确标注为模拟。", { exact: true })
    .waitFor();
  check(
    (await page.getByLabel("业务依据", { exact: true }).inputValue()) !== "",
    "risk signal archives explicit synthetic source before task creation",
  );
  const user = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("sg_user")),
  );
  const title = "P5浏览器验收-" + Date.now();
  await page.getByLabel("任务名称", { exact: true }).fill(title);
  await page.getByLabel("新任务责任人", { exact: true }).selectOption(user.id);
  await page
    .getByLabel("新任务措施", { exact: true })
    .fill("仅验收：联系物流核实，记录替代措施，不实际发送或采购");
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/workspace/tasks") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "创建处置任务", exact: true }).click();
  const createdResponse = await created;
  check(
    createdResponse.status() === 200,
    "task persisted through real authenticated API",
  );
  const task = await createdResponse.json();
  const detail = page.getByTestId("task-detail");
  await detail
    .getByRole("heading", { name: title + " · 待认领", exact: true })
    .waitFor();
  await detail.getByRole("button", { name: "开始处理", exact: true }).click();
  await detail
    .getByRole("heading", { name: title + " · 处理中", exact: true })
    .waitFor();
  const token = await page.evaluate(() => localStorage.getItem("sg_token"));
  const competing = await page.request.patch(
    `http://127.0.0.1:3100/api/v1/workspace/tasks/${task.id}`,
    {
      headers: {
        Authorization: "Bearer " + token,
        "Idempotency-Key": "browser-race-" + Date.now(),
      },
      data: { expected_version: 2, action: "assign", assignee_id: user.id },
    },
  );
  check(
    competing.status() === 200,
    "competing collaborator update commits before stale browser action",
  );
  await page.getByLabel("执行费用", { exact: true }).fill("1140.00");
  await page
    .getByLabel("结果与验证说明", { exact: true })
    .fill("措施记录已完成，费用为模拟验收输入，待人工验证");
  await detail.getByRole("button", { name: "提交验证", exact: true }).click();
  await page.getByRole("alert").filter({ hasText: "任务已被更新" }).waitFor();
  check(
    true,
    "stale browser edit is rejected with a visible version-conflict explanation",
  );
  await page.getByRole("button", { name: "重新加载核对", exact: true }).click();
  await detail.getByText("版本 3", { exact: true }).waitFor();
  await page.getByLabel("执行费用", { exact: true }).fill("1140.00");
  await page
    .getByLabel("结果与验证说明", { exact: true })
    .fill("重新加载核对后提交验证，费用是模拟输入");
  await detail.getByRole("button", { name: "提交验证", exact: true }).click();
  await detail
    .getByRole("heading", { name: title + " · 待验证", exact: true })
    .waitFor();
  await page
    .getByLabel("结果与验证说明", { exact: true })
    .fill("人工验收核对通过，仅完成处置记录，不代表真实业务收益");
  await detail
    .getByRole("button", { name: "验证通过并完成", exact: true })
    .click();
  await detail
    .getByRole("heading", { name: title + " · 已完成", exact: true })
    .waitFor();
  check(
    (await detail.textContent()).includes("1140.00"),
    "execution cost remains explicit human-entered value",
  );
  check(
    (await detail.locator("details").count()) === 5,
    "create, collaborator update and three transitions have audit replay",
  );
  check(
    await page.getByLabel("执行费用", { exact: true }).isDisabled(),
    "closed task inputs are read-only",
  );
  await detail.screenshot({
    path: path.join(output, "task-completed-1366.png"),
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "task page has no horizontal overflow at 1366",
  );
  await page.reload();
  await page.getByRole("button", { name: new RegExp(title) }).click();
  await page
    .getByTestId("task-detail")
    .getByRole("heading", { name: title + " · 已完成", exact: true })
    .waitFor();
  check(true, "task state survives browser refresh");
  await page.getByRole("link", { name: "企业数据", exact: true }).click();
  await page.getByTestId("workspace-page").waitFor();
  await page.getByRole("button", { name: "导入与预检", exact: true }).click();
  await page.getByLabel("导入对象", { exact: true }).selectOption("site");
  await page.getByLabel("内容来源", { exact: true }).selectOption("synthetic");
  const downloadTemplate = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载XLSX模板", exact: true }).click();
  const template = await downloadTemplate;
  await template.saveAs(path.join(output, "site-template.xlsx"));
  check(
    (await fs.readFile(path.join(output, "site-template.xlsx")))
      .subarray(0, 2)
      .toString() === "PK",
    "real XLSX template downloads",
  );
  const code = "BROWSER-" + Date.now();
  const headers = "站点编号,站点名称,类型,纬度,经度,国家\n";
  await page.getByLabel("数据文件", { exact: true }).setInputFiles({
    name: "mapped-site.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      headers + `${code},浏览器验收站点,factory,22.55,114.06,CN\n`,
    ),
  });
  await page.getByRole("button", { name: "读取表头", exact: true }).click();
  await page.getByLabel("映射 code", { exact: true }).waitFor();
  for (const [key, value] of Object.entries({
    code: "站点编号",
    name: "站点名称",
    site_type: "类型",
    latitude: "纬度",
    longitude: "经度",
    country: "国家",
  }))
    await page.getByLabel("映射 " + key, { exact: true }).selectOption(value);
  await page.getByRole("button", { name: "运行预检", exact: true }).click();
  await page.getByText("预检通过，尚未入库", { exact: false }).waitFor();
  check(true, "Chinese headers map to typed fields and pass preview");
  await page
    .getByRole("button", { name: "确认导入本企业", exact: true })
    .click();
  await page
    .getByRole("status")
    .getByText("确认导入完成，新增 1 条；重复确认不会重复新增。", {
      exact: true,
    })
    .waitFor();
  check(
    await page
      .getByRole("button", { name: "确认导入本企业", exact: true })
      .isDisabled(),
    "confirmed batch cannot be double-submitted in UI",
  );
  await page.getByLabel("数据文件", { exact: true }).setInputFiles({
    name: "invalid-site.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "code,name,site_type,latitude,longitude,country\n" +
        code +
        "-BAD,错误坐标,factory,91,114,CN\n",
    ),
  });
  await page.getByRole("button", { name: "读取表头", exact: true }).click();
  await page.getByLabel("映射 code", { exact: true }).waitFor();
  await page.getByRole("button", { name: "运行预检", exact: true }).click();
  await page.getByText("预检有错误，禁止确认", { exact: false }).waitFor();
  check(
    await page
      .getByRole("button", { name: "确认导入本企业", exact: true })
      .isDisabled(),
    "invalid coordinates show row errors and prevent commit",
  );
  await page
    .getByTestId("import-preview")
    .screenshot({ path: path.join(output, "import-error-1366.png") });
  await page.getByRole("button", { name: "企业记录", exact: true }).click();
  await page.getByLabel("记录类型", { exact: true }).selectOption("site");
  await page.getByLabel("搜索企业记录", { exact: true }).fill(code);
  await page
    .getByRole("button", { name: "浏览器验收站点", exact: true })
    .click();
  check(
    await page.getByText("记录与来源明细", { exact: true }).isVisible(),
    "imported business record can be queried with provenance",
  );
  await page.getByRole("button", { name: "报告中心", exact: true }).click();
  const reportResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/workspace/reports") &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "风险报告 XLSX", exact: true })
    .click();
  const exported = await reportResponse;
  check(exported.status() === 200, "real report generation succeeds");
  const report = await exported.json();
  const reportCard = page.getByTestId("workspace-report-" + report.id);
  await reportCard.waitFor();
  const downloadPromise = page.waitForEvent("download");
  await reportCard
    .getByRole("button", { name: "下载报告", exact: true })
    .click();
  const downloaded = await downloadPromise;
  await downloaded.saveAs(path.join(output, "browser-risk-report.xlsx"));
  const { createHash } = await import("node:crypto");
  check(
    createHash("sha256")
      .update(await fs.readFile(path.join(output, "browser-risk-report.xlsx")))
      .digest("hex") === report.sha256,
    "browser download exactly matches authenticated report SHA256",
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({
    path: path.join(output, "report-center-1920.png"),
    fullPage: true,
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "workspace has no horizontal overflow at 1920",
  );
  await page.getByRole("button", { name: "本地事件订阅", exact: true }).click();
  await page.getByRole("button", { name: "创建本地订阅", exact: true }).click();
  await page
    .getByText("本地订阅已创建，可读取已有和后续事件。", { exact: true })
    .waitFor();
  await page.getByRole("button", { name: "从头重放", exact: true }).click();
  await page
    .getByText(/task.created/)
    .first()
    .waitFor();
  check(
    await page.getByText(/仅本地保存，外发数量0/).isVisible(),
    "local event replay is explicit with zero external delivery",
  );
  await page.screenshot({
    path: path.join(output, "local-events-1920.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await login("admin");
  await page.getByRole("link", { name: "处置与复盘", exact: true }).click();
  await page.getByRole("button", { name: new RegExp(title) }).click();
  await page
    .getByTestId("task-detail")
    .getByRole("heading", { name: title + " · 已完成", exact: true })
    .waitFor();
  check(true, "same-enterprise admin can collaborate on shared task");
  check(errors.length === 0, "no uncaught browser errors");
  check(
    external.length === 0,
    "no external map/model/message calls during P5 workflows",
  );
  await context.close();
  await fs.writeFile(
    path.join(output, "browser.json"),
    JSON.stringify(
      {
        status: "passed",
        checked_at: new Date().toISOString(),
        task_id: task.id,
        report_id: report.id,
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
