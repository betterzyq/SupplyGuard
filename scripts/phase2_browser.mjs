/** P2 browser checks: WebGL, linked views, replay boundaries, offline reload and workload. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(
  root,
  process.env.SUPPLYGUARD_BROWSER_OUTPUT || ".local/acceptance/phase-2",
);
await fs.mkdir(output, { recursive: true });
const { chromium } = await import(
  path.join(root, ".local/browser-qa/node_modules/playwright/index.mjs")
);
const { default: pngjs } = await import(
  path.join(root, ".local/browser-qa/node_modules/pngjs/lib/png.js")
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
  check(
    /3,380,000/.test(await page.getByTestId("exposure-value").innerText()),
    "accepted P1 business overview remains correct",
  );
  const started = Date.now();
  await page.getByRole("link", { name: "风险控制塔", exact: true }).click();
  await page
    .locator('[data-testid="network-map"][data-map-ready="true"]')
    .waitFor({ timeout: 45000 });
  const firstMapMs = Date.now() - started;
  check(true, "embedded MapLibre/deck WebGL map ready");
  check(
    /3,380,000/.test(await page.getByTestId("map-exposure").innerText()),
    "map exposure equals accepted scenario total",
  );
  check(
    (await page.locator(".maplibregl-canvas").count()) === 1,
    "actual interactive basemap canvas exists",
  );
  await page.waitForFunction(() => {
    const canvas = document.querySelector(".maplibregl-canvas");
    return (
      canvas?.clientHeight >= 400 &&
      window.__supplyguardMap?.queryRenderedFeatures().length > 0
    );
  });
  await page.waitForTimeout(900);
  const mapPixels = pngjs.PNG.sync.read(
    await page.getByTestId("network-map").screenshot(),
  );
  let landPixels = 0,
    oceanPixels = 0,
    routePixels = 0;
  for (let i = 0; i < mapPixels.data.length; i += 4) {
    const [r, g, b] = mapPixels.data.subarray(i, i + 3);
    if (Math.abs(r - 21) < 4 && Math.abs(g - 40) < 4 && Math.abs(b - 59) < 4)
      landPixels++;
    if (Math.abs(r - 8) < 4 && Math.abs(g - 18) < 4 && Math.abs(b - 30) < 4)
      oceanPixels++;
    if (r > 180 && g > 120 && b < 100) routePixels++;
  }
  check(
    landPixels > 5000 && oceanPixels > 5000 && routePixels > 50,
    "painted map contains actual land, ocean and business routes (pixel assertion)",
  );
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "1366px control tower no page overflow",
  );
  await page.evaluate(() => document.querySelector("main")?.scrollTo(0, 0));
  await page.screenshot({
    path: path.join(output, "control-tower-1366.png"),
    fullPage: true,
  });
  const cluster = await page.evaluate(() => {
    const map = window.__supplyguardMap;
    const feature = map.queryRenderedFeatures({ layers: ["site-clusters"] })[0];
    const point = map.project(feature.geometry.coordinates);
    const box = map.getCanvas().getBoundingClientRect();
    return { x: box.x + point.x, y: box.y + point.y, zoom: map.getZoom() };
  });
  await page.mouse.click(cluster.x, cluster.y);
  await page.waitForFunction(
    (zoom) => window.__supplyguardMap.getZoom() > zoom + 0.1,
    cluster.zoom,
  );
  await page.waitForTimeout(650);
  check(true, "clicking geographic cluster expands sites");
  const node = await page.evaluate(() => {
    const map = window.__supplyguardMap;
    const feature = map.queryRenderedFeatures({ layers: ["site-nodes"] })[0];
    const point = map.project(feature.geometry.coordinates);
    const box = map.getCanvas().getBoundingClientRect();
    return {
      x: box.x + point.x,
      y: box.y + point.y,
      name: feature.properties.name,
    };
  });
  await page.mouse.click(node.x, node.y);
  await page
    .getByTestId("network-detail")
    .getByRole("heading", { name: node.name, exact: true })
    .waitFor();
  check(true, "clicking painted geographic site opens correct details");
  await page
    .getByRole("button", { name: "宁波港集装箱作业拥堵", exact: false })
    .click();
  await page
    .getByTestId("network-detail")
    .getByRole("heading", { name: "宁波港", exact: true })
    .waitFor();
  check(true, "risk event selects matching geographic site");
  await page
    .getByTestId("network-detail")
    .getByRole("button", { name: /SHP-001/ })
    .click();
  await page
    .getByTestId("network-detail")
    .getByRole("heading", { name: "SHP-001", exact: true })
    .waitFor();
  check(
    await page
      .getByTestId("network-detail")
      .getByText(/模拟轨迹插值/)
      .isVisible(),
    "shipment detail labels simulated position",
  );
  await page
    .getByTestId("network-detail")
    .getByRole("button", { name: /查看业务依赖/ })
    .click();
  await page.getByTestId("business-dependency").waitFor();
  await page.waitForFunction(
    () =>
      document.querySelectorAll(
        '[data-testid="business-dependency"] .react-flow__edge',
      ).length > 0,
  );
  check(true, "order drilldown renders connected business dependency graph");
  await page.getByTestId("business-dependency").screenshot({
    path: path.join(output, "order-dependency-1366.png"),
  });
  await page.getByRole("button", { name: "地理网络", exact: true }).click();
  await page.locator('[data-map-ready="true"]').waitFor();
  await page.getByLabel("供应商筛选").selectOption("V-001");
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="map-exposure"]')
      ?.textContent.includes("2,240,000"),
  );
  const server = await page.evaluate(async () => {
    const token = localStorage.getItem("sg_token");
    return (
      await fetch("/api/v1/business/network?supplier_id=V-001", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
  });
  check(
    server.metrics.exposure_amount_cny === "2240000.00",
    "client filter and backend exposure agree",
  );
  check(
    Number(
      await page.getByTestId("network-map").getAttribute("data-map-routes"),
    ) === server.shipments.length,
    "filtered map routes and backend shipments agree",
  );
  await page
    .getByRole("link", { name: "物流跟踪", exact: true })
    .first()
    .click();
  await page.getByRole("heading", { name: "物流跟踪", exact: true }).waitFor();
  check(
    (await page.getByLabel("供应商筛选").inputValue()) === "V-001",
    "supplier filter persists between risk and logistics views",
  );
  await page.getByRole("link", { name: "风险控制塔", exact: true }).click();
  await page.locator('[data-map-ready="true"]').waitFor();
  await page.getByRole("button", { name: "重置筛选", exact: true }).click();
  await page.getByLabel("回放时间").fill("120");
  await page.waitForFunction(() =>
    /(?:¥|￥)0\.00/.test(
      document.querySelector('[data-testid="map-exposure"]')?.textContent || "",
    ),
  );
  check(
    await page
      .getByText("当前时点或筛选范围内暂无已发现事件", { exact: true })
      .isVisible(),
    "early replay does not reveal future risk events",
  );
  await page
    .getByRole("link", { name: "物流跟踪", exact: true })
    .first()
    .click();
  await page.getByRole("heading", { name: "物流跟踪", exact: true }).waitFor();
  await page.locator('[data-map-ready="true"]').waitFor();
  check(
    await page
      .getByTestId("network-detail")
      .getByText("较原计划 +0 小时", { exact: true })
      .isVisible(),
    "replay time persists across map and tracking, no future ETA update",
  );
  await page
    .getByRole("button", { name: "返回演示最新时点", exact: true })
    .click();
  await page
    .getByTestId("network-detail")
    .getByText("较原计划 +18 小时", { exact: true })
    .waitFor();
  await page.getByRole("button", { name: "播放回放", exact: true }).click();
  await page.getByRole("button", { name: "暂停回放", exact: true }).waitFor();
  await page.waitForTimeout(900);
  await page.getByRole("button", { name: "暂停回放", exact: true }).click();
  const slider = Number(await page.getByLabel("回放时间").inputValue());
  check(slider > 0 && slider < 540, "timeline play advances and pauses");
  await page
    .getByRole("button", { name: "返回演示最新时点", exact: true })
    .click();
  await page.getByLabel("场景", { exact: true }).selectOption("tier2-shutdown");
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="map-exposure"]')
      ?.textContent.includes("3,860,000"),
  );
  await page.getByLabel("场景", { exact: true }).selectOption("regional-flood");
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="map-exposure"]')
      ?.textContent.includes("1,780,000"),
  );
  check(
    true,
    "three manufacturing scenarios update tracking and exposure consistently",
  );
  await page.getByLabel("搜索订单或批次").fill("SHP-003");
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="network-map"]')
        ?.getAttribute("data-map-routes") === "1",
  );
  check(
    await page
      .getByTestId("network-detail")
      .getByRole("heading", { name: "SHP-003", exact: true })
      .isVisible(),
    "shipment search keeps detail within filtered results",
  );
  await page.getByRole("button", { name: "重置筛选", exact: true }).click();
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({
    path: path.join(output, "tracking-1920.png"),
    fullPage: true,
  });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "1920px tracking no page overflow",
  );
  await page.getByRole("button", { name: "准备离线演示", exact: true }).click();
  await page
    .getByText("离线演示已准备：可断网刷新地图与物流页，并回放三个场景。", {
      exact: true,
    })
    .waitFor({ timeout: 45000 });
  check(
    true,
    "public application assets and three synthetic snapshots prepared offline",
  );
  await context.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator('[data-map-ready="true"]').waitFor({ timeout: 45000 });
  await page.getByText(/离线演示：仅使用已缓存的合成快照/).waitFor();
  await page
    .getByLabel("场景", { exact: true })
    .selectOption("port-congestion");
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="map-exposure"]')
      ?.textContent.includes("3,380,000"),
  );
  await page.getByLabel("回放时间").fill("0");
  await page.waitForFunction(() =>
    /(?:¥|￥)0\.00/.test(
      document.querySelector('[data-testid="map-exposure"]')?.textContent || "",
    ),
  );
  check(
    true,
    "network-disconnected reload, scenario switching and timeline remain interactive",
  );
  await page.screenshot({
    path: path.join(output, "offline-tracking-1920.png"),
    fullPage: true,
  });
  const cachedUrls = await page.evaluate(async () => {
    const cache = await caches.open("supplyguard-public-map-v2");
    return (await cache.keys()).map((r) => new URL(r.url).pathname);
  });
  check(
    !cachedUrls.some((u) => u.startsWith("/api/") || u.startsWith("/auth")),
    "service worker never caches authentication or API responses",
  );
  await context.setOffline(false);
  await page.reload();
  await page.locator('[data-map-ready="true"]').waitFor({ timeout: 45000 });
  await page.goto(
    "http://127.0.0.1:3100/tracking?scenario=port-congestion&at=2026-10-16T02%3A00%3A00%2B08%3A00&shipment=SHP-001&supplier=V-001",
  );
  await page
    .getByTestId("network-detail")
    .getByRole("heading", { name: "SHP-001", exact: true })
    .waitFor();
  check(
    (await page.getByLabel("回放时间").inputValue()) === "120" &&
      (await page.getByLabel("供应商筛选").inputValue()) === "V-001",
    "shared URL restores shipment, supplier and replay time",
  );
  await page.goto("http://127.0.0.1:3100/supply-chain?fallback=1");
  await page.getByTestId("map-fallback").waitFor();
  check(
    await page
      .getByRole("heading", { name: "关联交付订单", exact: true })
      .isVisible(),
    "WebGL failure retains useful order and site lists",
  );
  await page.goto("http://127.0.0.1:3100/supply-chain");
  await page.locator('[data-map-ready="true"]').waitFor();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await page.getByRole("heading", { name: "登录", exact: true }).waitFor();
  check(
    (await page.evaluate(
      () =>
        Object.keys(localStorage).filter((k) => k.startsWith("sg-network-v2:"))
          .length,
    )) === 0,
    "logout clears per-user synthetic data cache",
  );
  await page.getByLabel("邮箱", { exact: true }).fill("admin@example.com");
  await page
    .getByLabel("密码", { exact: true })
    .fill(process.env.SUPPLYGUARD_DEMO_PASSWORD || "password123");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByTestId("exposure-value").waitFor();
  await page.goto("http://127.0.0.1:3100/supply-chain?benchmark=1");
  await page
    .locator(
      '[data-map-ready="true"][data-map-sites="1000"][data-map-routes="2000"]',
    )
    .waitFor({ timeout: 45000 });
  const performance = await page.evaluate(async () => {
    const map = window.__supplyguardMap;
    const samples = [];
    const render = () => samples.push(performance.now());
    map.on("render", render);
    const start = performance.now();
    map.easeTo({ center: [114, 30], zoom: 4.6, duration: 2200 });
    await new Promise((resolve) => map.once("moveend", resolve));
    map.off("render", render);
    return {
      frames: samples.length,
      elapsed_ms: performance.now() - start,
      renders_per_second: samples.length / ((performance.now() - start) / 1000),
    };
  });
  check(
    performance.frames > 5,
    "1000 sites and 2000 routes remain interactive during camera movement",
  );
  const cdp = await context.newCDPSession(page);
  await cdp.send("Performance.enable");
  const runtimeMetrics = await cdp.send("Performance.getMetrics");
  const heap = runtimeMetrics.metrics.find(
    (m) => m.name === "JSHeapUsedSize",
  )?.value;
  await page.screenshot({
    path: path.join(output, "map-workload-1000-2000.png"),
    fullPage: true,
  });
  check(
    external.length === 0,
    "map operation makes no external network requests",
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
        first_map_ready_ms: firstMapMs,
        video: path.relative(root, await page.video().path()),
        workload: {
          sites: 1000,
          routes: 2000,
          rendering: "Chromium SwiftShader software WebGL, CPU only",
          viewport: "1920x1080",
          ...performance,
          js_heap_used_bytes: heap,
        },
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
