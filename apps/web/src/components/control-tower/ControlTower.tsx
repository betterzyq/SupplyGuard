"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Box,
  DownloadCloud,
  MapPin,
  Pause,
  Play,
  RotateCcw,
  Search,
  Ship,
  Truck,
  WifiOff,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import {
  businessDate,
  moneyCny,
  riskLabels,
  useBusinessScenario,
} from "@/lib/business";
import {
  getNetworkSnapshot,
  modeLabels,
  prepareOfflineDemo,
  projectNetwork,
  siteLabels,
  useNetworkFilters,
} from "@/lib/network";
import { benchmarkNetwork } from "@/lib/network-benchmark";
const NetworkMap = dynamic(() => import("./NetworkMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center rounded-2xl bg-slate-900 text-sm text-slate-400">
      加载地图组件…
    </div>
  ),
});
const DependencyGraph = dynamic(() => import("./DependencyGraph"), {
  ssr: false,
});

export default function ControlTower({ view }: { view: "risk" | "tracking" }) {
  const user = useAuthStore((s) => s.user);
  const { scenarioId, selectScenario, atTime, setAtTime } =
    useBusinessScenario();
  const {
    supplierId,
    setSupplierId,
    mode,
    setMode,
    search,
    setSearch,
    riskOnly,
    setRiskOnly,
  } = useNetworkFilters();
  const pendingLink = useRef<URLSearchParams | null>(null);
  const [linkReady, setLinkReady] = useState(false);
  const [selectedSite, setSelectedSite] = useState<string | null>(null);
  const [selectedShipment, setSelectedShipment] = useState<string | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<string | null>(null);
  const [showLocationOverview, setShowLocationOverview] = useState(false);
  const detailPanel = useRef<HTMLElement | null>(null);
  const locationHeading = useRef<HTMLHeadingElement | null>(null);
  const [showGraph, setShowGraph] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [offline, setOffline] = useState(false);
  const [offlineNote, setOfflineNote] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [layers, setLayers] = useState({
    risk: true,
    plans: true,
    tracks: true,
    dependencies: false,
  });
  const [fallback, setFallback] = useState(false);
  const [benchmark, setBenchmark] = useState(false);
  const query = useQuery({
    queryKey: ["business-network-v2", user?.tenant_id, user?.id, scenarioId],
    queryFn: () => getNetworkSnapshot(user!, scenarioId),
    enabled: !!user,
    networkMode: "always",
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 300000,
  });
  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    navigator.serviceWorker
      ?.register("/map-sw.js")
      .catch(() => setOfflineNote("离线资源服务不可用，联网查看不受影响。"));
    const params = new URLSearchParams(window.location.search);
    if (
      params.has("scenario") &&
      !["port-congestion", "tier2-shutdown", "regional-flood"].includes(
        params.get("scenario")!,
      )
    )
      params.delete("scenario");
    setFallback(params.get("fallback") === "1");
    setBenchmark(
      params.get("benchmark") === "1" && !!user?.roles.includes("admin"),
    );
    pendingLink.current = params;
    if (
      params.has("scenario") &&
      ["port-congestion", "tier2-shutdown", "regional-flood"].includes(
        params.get("scenario")!,
      )
    )
      selectScenario(params.get("scenario")!);
    if (params.has("supplier")) setSupplierId(params.get("supplier") || "");
    if (params.has("mode")) setMode(params.get("mode") || "");
    if (params.has("q")) setSearch(params.get("q") || "");
    if (params.has("risk")) setRiskOnly(params.get("risk") === "1");
    if (params.has("at") && Number.isFinite(Date.parse(params.get("at")!)))
      setAtTime(params.get("at"));
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);
  useEffect(() => {
    setShowLocationOverview(false);
    setSelectedSite(null);
    setSelectedShipment(null);
    setSelectedOrder(null);
    setShowGraph(false);
    setPlaying(false);
  }, [scenarioId]);
  useEffect(() => {
    if (!query.data || !pendingLink.current) return;
    const params = pendingLink.current;
    if (
      params.has("scenario") &&
      params.get("scenario") !== query.data.scenario.id
    )
      return;
    setSelectedSite(params.get("site"));
    setSelectedShipment(params.get("shipment"));
    pendingLink.current = null;
    setLinkReady(true);
  }, [query.data]);
  useEffect(() => {
    if (!linkReady) return;
    const params = new URLSearchParams(window.location.search);
    const values: Record<string, string | null> = {
      scenario: scenarioId,
      at: atTime || null,
      supplier: supplierId || null,
      mode: mode || null,
      q: search || null,
      risk: riskOnly ? "1" : null,
      site: selectedSite,
      shipment: selectedShipment,
    };
    for (const [key, value] of Object.entries(values)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}?${params.toString()}`,
    );
  }, [
    linkReady,
    scenarioId,
    atTime,
    supplierId,
    mode,
    search,
    riskOnly,
    selectedSite,
    selectedShipment,
  ]);
  const data = useMemo(
    () =>
      query.data
        ? projectNetwork(query.data, {
            atTime,
            supplierId,
            mode,
            search,
            riskOnly,
          })
        : null,
    [query.data, atTime, supplierId, mode, search, riskOnly],
  );
  const mapData = useMemo(
    () => (data && benchmark ? benchmarkNetwork(data) : data),
    [data, benchmark],
  );
  useEffect(() => {
    if (!data) return;
    if (selectedSite && !data.sites.some((s) => s.id === selectedSite))
      setSelectedSite(null);
    if (
      selectedShipment &&
      !data.shipments.some((s) => s.id === selectedShipment)
    )
      setSelectedShipment(null);
    if (selectedOrder && !data.orders.some((s) => s.id === selectedOrder)) {
      setSelectedOrder(null);
      setShowGraph(false);
    }
  }, [data]);
  useEffect(() => {
    if (!query.data || !playing) return;
    const timer = setInterval(() => {
      const next = Math.min(
        Date.parse(atTime || query.data!.timeline.start_at) + 15 * 60000,
        Date.parse(query.data!.timeline.end_at),
      );
      setAtTime(new Date(next).toISOString());
      if (next >= Date.parse(query.data!.timeline.end_at)) setPlaying(false);
    }, 750);
    return () => clearInterval(timer);
  }, [playing, atTime, query.data, setAtTime]);
  const ship =
    data?.shipments.find((s) => s.id === selectedShipment) ||
    (view === "tracking" && !selectedSite && !showLocationOverview
      ? data?.shipments[0]
      : undefined);
  const site = data?.sites.find((s) => s.id === selectedSite);
  const order = data?.orders.find((o) => o.id === selectedOrder);
  const selectShip = (id: string) => {
    setShowLocationOverview(false);
    setSelectedShipment(id);
    setSelectedSite(null);
    setShowGraph(false);
  };
  const selectSite = (id: string) => {
    setShowLocationOverview(false);
    setSelectedSite(id);
    setSelectedShipment(null);
    setShowGraph(false);
  };
  const returnToLocations = () => {
    setSelectedSite(null);
    setSelectedShipment(null);
    setSelectedOrder(null);
    setShowGraph(false);
    setShowLocationOverview(true);
    requestAnimationFrame(() => {
      detailPanel.current?.scrollTo(0, 0);
      locationHeading.current?.focus({ preventScroll: true });
    });
  };
  const resetFilters = () => {
    setSupplierId("");
    setMode("");
    setSearch("");
    setRiskOnly(false);
    setSelectedSite(null);
    setSelectedShipment(null);
    setSelectedOrder(null);
    setShowGraph(false);
  };
  if (query.isPending)
    return <p className="p-8 text-slate-500">正在加载供应网络…</p>;
  if (query.isError || !data || !mapData)
    return (
      <div
        role="alert"
        className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900"
      >
        <h1 className="font-semibold">供应网络暂不可用</h1>
        <p className="mt-3 text-sm">
          {query.error?.message || "没有可用演示快照"}
        </p>
        <button
          onClick={() => query.refetch()}
          className="mt-4 rounded-lg border border-amber-300 px-4 py-2 text-sm"
        >
          重试
        </button>
      </div>
    );
  const timelineStart = Date.parse(data.timeline.start_at),
    timelineEnd = Date.parse(data.timeline.end_at),
    current = Date.parse(data.as_of);
  const isAdmin = !!user?.roles.includes("admin");
  return (
    <div className="mx-auto max-w-[1800px] space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.2em] text-slate-400">
            {view === "risk" ? "RISK CONTROL TOWER" : "SHIPMENT VISIBILITY"}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            {view === "risk" ? "供应链风险控制塔" : "物流跟踪"}
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            {view === "risk"
              ? "从风险发生地点，追踪站点、物料与交付订单的关联。"
              : "沿运输批次查看计划路线、回放位置与交付里程碑。"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href={view === "risk" ? "/tracking" : "/supply-chain"}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600"
          >
            {view === "risk" ? "物流跟踪" : "风险控制塔"} →
          </Link>
          <button
            disabled={preparing || offline}
            onClick={async () => {
              setPreparing(true);
              setOfflineNote("");
              try {
                await prepareOfflineDemo(user!);
                setOfflineNote(
                  "离线演示已准备：可断网刷新地图与物流页，并回放三个场景。",
                );
              } catch (e) {
                setOfflineNote((e as Error).message);
              } finally {
                setPreparing(false);
              }
            }}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs text-white disabled:opacity-50"
          >
            <DownloadCloud className="h-3 w-3" />
            {preparing ? "准备中…" : "准备离线演示"}
          </button>
        </div>
      </div>
      {(offline || offlineNote) && (
        <p
          role="status"
          className={`flex items-center gap-2 rounded-lg border p-3 text-xs ${offline ? "border-amber-200 bg-amber-50 text-amber-800" : "border-cyan-100 bg-cyan-50 text-cyan-800"}`}
        >
          <WifiOff className="h-3 w-3" />
          {offline
            ? "离线演示：仅使用已缓存的合成快照，无法验证实时登录；管理与写入功能不可用。"
            : offlineNote}
        </p>
      )}
      {benchmark && (
        <p className="rounded-lg bg-violet-50 p-3 text-xs text-violet-800">
          管理员地图规模自测：1,000 个合成站点 / 2,000
          条合成路线；不代表实际业务覆盖或订单规模。
          <Link href="/supply-chain" className="ml-3 underline">
            退出规模自测
          </Link>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <select
          aria-label="场景"
          value={scenarioId}
          onChange={(e) => {
            selectScenario(e.target.value);
            resetFilters();
          }}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
        >
          {data.scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <label className="flex min-w-[180px] flex-1 items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <Search className="h-3 w-3 text-slate-400" />
          <input
            aria-label="搜索订单或批次"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="订单、批次、供应商或客户"
            className="w-full min-w-0 bg-transparent text-xs outline-none"
          />
        </label>
        <select
          aria-label="供应商筛选"
          value={supplierId}
          onChange={(e) => setSupplierId(e.target.value)}
          className="max-w-[175px] rounded-lg border border-slate-200 px-3 py-2 text-xs"
        >
          <option value="">全部供应商</option>
          {data.suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          aria-label="运输方式"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
        >
          <option value="">全部运输方式</option>
          {Object.entries(modeLabels).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 px-2 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={riskOnly}
            onChange={(e) => setRiskOnly(e.target.checked)}
          />
          仅风险订单
        </label>
        <button
          aria-label="重置筛选"
          onClick={resetFilters}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          {
            label: "筛选内风险敞口",
            value: moneyCny(data.metrics.exposure_amount_cny),
            sub: "唯一未交付订单金额 · 非预计损失",
          },
          {
            label: "风险订单 / 可见订单",
            value: `${data.metrics.at_risk_orders} / ${data.metrics.visible_orders}`,
            sub: "以当前场景、筛选和时点计算",
          },
          {
            label: "可见站点 / 运输批次",
            value: benchmark
              ? "1000 / 2000"
              : `${data.metrics.visible_sites} / ${data.metrics.visible_shipments}`,
            sub: benchmark
              ? "性能测试合成几何"
              : "地图、列表与批次详情共用数据",
          },
          {
            label: "已出现风险事件",
            value: `${data.metrics.active_risk_events}`,
            sub: `${businessDate(data.as_of)} · 北京时间`,
          },
        ].map((m) => (
          <div
            key={m.label}
            className="rounded-xl border border-slate-200 bg-white px-4 py-3"
          >
            <p className="text-[10px] text-slate-500">{m.label}</p>
            <p
              className="mt-1 text-xl font-semibold tabular-nums text-slate-900"
              data-testid={
                m.label === "筛选内风险敞口" ? "map-exposure" : undefined
              }
            >
              {m.value}
            </p>
            <p className="mt-1 text-[10px] text-slate-400">{m.sub}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="mr-1 text-slate-400">风险信号</span>
        {data.risk_events.length ? (
          data.risk_events.map((e) => (
            <button
              key={e.id}
              onClick={() => selectSite(e.site_ids[0])}
              className="flex items-center gap-2 rounded-full border border-rose-100 bg-rose-50 px-3 py-1.5 text-rose-700"
            >
              <AlertTriangle className="h-3 w-3" />
              {e.name}
              <ArrowRight className="h-3 w-3" />
            </button>
          ))
        ) : (
          <span className="text-slate-400">
            当前时点或筛选范围内暂无已发现事件
          </span>
        )}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex gap-1">
              <button
                onClick={() => setShowGraph(false)}
                className={`rounded-lg px-3 py-1.5 text-xs ${!showGraph ? "bg-slate-900 text-white" : "text-slate-500"}`}
              >
                地理网络
              </button>
              <button
                disabled={!order}
                onClick={() => setShowGraph(true)}
                className={`rounded-lg px-3 py-1.5 text-xs disabled:opacity-40 ${showGraph ? "bg-slate-900 text-white" : "text-slate-500"}`}
              >
                业务依赖{order ? ` · ${order.id}` : "（先选择订单）"}
              </button>
            </div>
            <div className="flex flex-wrap gap-3 text-[10px] text-slate-500">
              {[
                { id: "risk", name: "风险区" },
                { id: "plans", name: "计划路线" },
                { id: "tracks", name: "回放轨迹" },
                { id: "dependencies", name: "依赖关联" },
              ].map(({ id, name }) => (
                <label key={id} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={layers[id as keyof typeof layers]}
                    onChange={(e) =>
                      setLayers({ ...layers, [id]: e.target.checked })
                    }
                  />
                  {name}
                </label>
              ))}
            </div>
          </div>
          <div className="h-[460px] 2xl:h-[560px]">
            {showGraph && order ? (
              <div className="h-full rounded-2xl border border-slate-200 bg-white p-4">
                <p className="mb-3 text-xs text-slate-500">
                  同一制造演示数据中的供应商 → 物料 → 产品 → 订单 →
                  客户；关系不等同于实际运输轨迹。
                </p>
                <DependencyGraph order={order} />
                <button
                  onClick={() => setShowGraph(false)}
                  className="mt-3 text-xs text-cyan-700"
                >
                  ← 返回地图
                </button>
              </div>
            ) : (
              <NetworkMap
                data={mapData}
                selectedSite={selectedSite}
                selectedShipment={ship?.id || selectedShipment}
                onSite={selectSite}
                onShipment={selectShip}
                layers={layers}
                forceFallback={fallback}
              />
            )}
          </div>
          <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <button
                  aria-label={playing ? "暂停回放" : "播放回放"}
                  onClick={() => {
                    if (!playing && current >= timelineEnd)
                      setAtTime(data.timeline.start_at);
                    setPlaying(!playing);
                  }}
                  className="rounded-lg bg-slate-900 p-2 text-white"
                >
                  {playing ? (
                    <Pause className="h-3 w-3" />
                  ) : (
                    <Play className="h-3 w-3" />
                  )}
                </button>
                <p className="text-xs font-medium text-slate-700">
                  历史情景回放{" "}
                  <span className="ml-2 text-slate-400">
                    {businessDate(data.as_of)}
                  </span>
                </p>
              </div>
              <button
                onClick={() => {
                  setPlaying(false);
                  setAtTime(null);
                }}
                className="text-[10px] text-cyan-700"
              >
                返回演示最新时点
              </button>
            </div>
            <input
              aria-label="回放时间"
              type="range"
              min={0}
              max={(timelineEnd - timelineStart) / 60000}
              step={5}
              value={(current - timelineStart) / 60000}
              onChange={(e) => {
                setPlaying(false);
                setAtTime(
                  new Date(
                    timelineStart + Number(e.target.value) * 60000,
                  ).toISOString(),
                );
              }}
              className="w-full accent-cyan-600"
            />
            <div className="mt-1 flex justify-between text-[10px] text-slate-400">
              <span>{businessDate(data.timeline.start_at)}</span>
              <span>轨迹、事件、里程碑与 ETA 更新均截断至所选时点</span>
              <span>{businessDate(data.timeline.end_at)}</span>
            </div>
          </div>
        </section>
        <aside
          ref={detailPanel}
          className="max-h-[690px] space-y-3 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4"
          data-testid="network-detail"
        >
          {(site || ship || order) && (
            <div className="sticky top-0 z-10 bg-white pb-2">
              <button
                type="button"
                onClick={returnToLocations}
                title="返回“从地点查看业务影响”，重新选择站点"
                className="flex w-full items-center gap-2 rounded-lg border border-cyan-100 bg-cyan-50 px-3 py-2 text-left text-xs font-medium text-cyan-800 hover:bg-cyan-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-600"
              >
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                返回地点列表
              </button>
            </div>
          )}
          {ship && !site ? (
            <>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Truck className="h-4 w-4 text-cyan-600" />
                运输批次详情
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                {ship.id}
              </h2>
              <p className="text-xs text-slate-400">
                {modeLabels[ship.mode]} · {ship.carrier}
              </p>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-[10px] text-slate-400">当前演示 ETA</p>
                <p className="mt-1 text-sm font-medium text-slate-800">
                  {businessDate(ship.eta)}
                </p>
                <p className="mt-2 text-xs text-amber-700">
                  较原计划 +{ship.delay_hours} 小时
                </p>
                <p className="mt-2 text-[10px] leading-relaxed text-slate-400">
                  {ship.eta_source}
                  <br />
                  {ship.eta_reason}
                </p>
              </div>
              <p className="text-[10px] leading-relaxed text-slate-400">
                {ship.position_source}
                <br />
                位置截至{" "}
                {ship.position
                  ? businessDate(ship.position.at)
                  : "尚无回放记录"}
              </p>
              <div className="space-y-4 border-l border-slate-200 pl-3">
                {ship.milestones.map((m) => (
                  <div key={m.name}>
                    <p
                      className={`text-xs font-medium ${m.observed_at ? "text-cyan-700" : "text-slate-400"}`}
                    >
                      {m.observed_at ? "●" : "○"} {m.name}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-400">
                      计划 {businessDate(m.planned_at)}
                      <br />
                      {m.observed_at
                        ? `回放记录 ${businessDate(m.observed_at)}`
                        : "当前时点尚无完成记录"}
                    </p>
                  </div>
                ))}
              </div>
              <p className="pt-2 text-xs font-medium text-slate-700">
                关联订单
              </p>
              {data.orders
                .filter((o) => ship.order_ids.includes(o.id))
                .map((o) => (
                  <button
                    key={o.id}
                    onClick={() => {
                      setSelectedOrder(o.id);
                      setShowGraph(true);
                    }}
                    className="w-full rounded-lg border border-slate-200 p-3 text-left text-xs"
                  >
                    <p className="font-medium text-slate-700">{o.id}</p>
                    <p className="mt-1 text-slate-400">
                      {o.product_name} · {moneyCny(o.amount_cny)}
                    </p>
                    <p className="mt-2 text-cyan-700">查看业务依赖 →</p>
                  </button>
                ))}
            </>
          ) : site ? (
            <>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <MapPin className="h-4 w-4" />
                站点详情
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                {site.name}
              </h2>
              <p className="text-xs text-slate-500">
                {siteLabels[site.kind]} · {site.country} · {site.id}
              </p>
              <p className="text-[10px] text-slate-400">
                WGS84 {site.longitude.toFixed(3)}, {site.latitude.toFixed(3)}
              </p>
              {site.risk_event_ids.length > 0 && (
                <Link
                  href={`/simulation?scenario=${scenarioId}&event=${site.risk_event_ids[0]}&at=${encodeURIComponent(data.as_of)}`}
                  className="flex items-center justify-between rounded-lg border border-cyan-100 bg-cyan-50 p-3 text-xs font-medium text-cyan-800"
                >
                  模拟影响与方案
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              )}
              {site.risk_event_ids.length > 0 && (
                <Link
                  href={`/actions?demo_event=${site.risk_event_ids[0]}&scenario=${scenarioId}`}
                  className="rounded-lg border border-indigo-100 p-3 text-xs text-indigo-700"
                >
                  建立处置任务
                </Link>
              )}
              {data.risk_events
                .filter((e) => site.risk_event_ids.includes(e.id))
                .map((e) => (
                  <div key={e.id} className="rounded-xl bg-rose-50 p-3">
                    <p className="text-xs font-medium text-rose-700">
                      {e.name}
                    </p>
                    <p className="mt-2 text-[10px] leading-relaxed text-rose-600">
                      {e.description}
                    </p>
                    <p className="mt-2 text-[10px] text-rose-500">
                      {businessDate(e.detected_at)} · {riskLabels[e.severity]}
                    </p>
                  </div>
                ))}
              <p className="pt-2 text-xs font-medium text-slate-700">
                相关运输与订单
              </p>
              {data.shipments
                .filter(
                  (s) =>
                    s.origin_site_id === site.id ||
                    s.destination_site_id === site.id ||
                    data.orders.some(
                      (o) =>
                        s.order_ids.includes(o.id) &&
                        o.risk_event_ids.some((id) =>
                          site.risk_event_ids.includes(id),
                        ),
                    ),
                )
                .map((s) => (
                  <button
                    key={s.id}
                    onClick={() => selectShip(s.id)}
                    className="flex w-full justify-between rounded-lg border border-slate-200 p-3 text-xs text-slate-600"
                  >
                    <span>
                      {s.id} · {modeLabels[s.mode]}
                    </span>
                    <ArrowRight className="h-3 w-3" />
                  </button>
                ))}
              {data.orders
                .filter(
                  (o) =>
                    o.destination_site_id === site.id ||
                    o.risk_event_ids.some((id) =>
                      site.risk_event_ids.includes(id),
                    ),
                )
                .slice(0, 6)
                .map((o) => (
                  <button
                    key={o.id}
                    onClick={() => {
                      setSelectedOrder(o.id);
                      setShowGraph(true);
                    }}
                    className="w-full rounded-lg bg-slate-50 p-3 text-left text-xs text-slate-600"
                  >
                    {o.id}{" "}
                    <span className="float-right text-cyan-700">
                      业务依赖 →
                    </span>
                  </button>
                ))}
            </>
          ) : (
            <>
              <h2
                ref={locationHeading}
                tabIndex={-1}
                className="text-sm font-semibold text-slate-800 focus:outline-none"
              >
                从地点查看业务影响
              </h2>
              <p className="text-xs leading-relaxed text-slate-400">
                点击风险信号、地图站点或运输位置，查看同一时点的站点、运输批次与订单。重叠站点会聚合，点击可展开。
              </p>
              <div className="rounded-xl bg-cyan-50 p-3 text-xs leading-relaxed text-cyan-800">
                {data.scenario.decision_question}
              </div>
              <p className="text-xs text-slate-500">站点快捷选择</p>
              {data.sites.map((s) => (
                <button
                  key={s.id}
                  onClick={() => selectSite(s.id)}
                  className="flex w-full items-center justify-between rounded-lg border border-slate-100 p-2.5 text-left text-xs text-slate-600"
                >
                  <span>{s.name}</span>
                  <span
                    className={
                      s.risk_event_ids.length
                        ? "text-rose-500"
                        : "text-slate-300"
                    }
                  >
                    ●
                  </span>
                </button>
              ))}
            </>
          )}
        </aside>
      </div>
      <section className="rounded-2xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">
            {view === "tracking" ? "运输批次" : "关联交付订单"}
          </h2>
          <span className="text-[10px] text-slate-400">
            当前筛选 {data.orders.length} 笔订单 / {data.shipments.length}{" "}
            个批次 · {data.dataset_version}
          </span>
        </div>
        {view === "tracking" ? (
          <div className="grid gap-3 p-4 sm:grid-cols-2 2xl:grid-cols-4">
            {data.shipments.map((s) => (
              <button
                key={s.id}
                aria-pressed={ship?.id === s.id}
                onClick={() => selectShip(s.id)}
                className={`rounded-xl border p-4 text-left ${ship?.id === s.id ? "border-cyan-500 bg-cyan-50/60" : "border-slate-200"}`}
              >
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-slate-800">
                    {s.id}
                  </span>
                  <Ship className="h-4 w-4 text-slate-300" />
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  {modeLabels[s.mode]} · {s.order_ids.join(", ")}
                </p>
                <p className="mt-3 text-xs text-slate-600">
                  ETA {businessDate(s.eta)}
                </p>
                <p className="mt-1 text-[10px] text-amber-700">
                  计划调整 +{s.delay_hours} 小时
                </p>
              </button>
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-left text-xs">
              <thead className="bg-slate-50 text-slate-400">
                <tr>
                  {[
                    "订单",
                    "产品 / 供应商",
                    "金额",
                    "风险",
                    "运输批次",
                    "业务依赖",
                  ].map((h) => (
                    <th key={h} className="px-4 py-3 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.orders.map((o) => (
                  <tr key={o.id}>
                    <td className="px-4 py-3 font-medium text-slate-700">
                      {o.id}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {o.product_name}
                      <p className="mt-1 text-[10px] text-slate-400">
                        {o.supplier_name}
                      </p>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-slate-700">
                      {moneyCny(o.amount_cny)}
                    </td>
                    <td className="px-4 py-3 text-rose-600">
                      {o.severity ? riskLabels[o.severity] : "当前无场景风险"}
                    </td>
                    <td className="px-4 py-3">
                      {o.shipment_ids.length ? (
                        o.shipment_ids.map((id) => (
                          <button
                            key={id}
                            onClick={() => selectShip(id)}
                            className="mr-2 text-cyan-700 underline"
                          >
                            {id}
                          </button>
                        ))
                      ) : (
                        <span className="text-slate-400">暂无运输批次</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => {
                          setSelectedOrder(o.id);
                          setShowGraph(true);
                        }}
                        className="flex items-center gap-1 text-cyan-700"
                      >
                        <Box className="h-3 w-3" />
                        查看依赖
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!data.orders.length && (
          <p className="p-6 text-center text-sm text-slate-400">
            当前筛选没有匹配订单，可重置筛选。
          </p>
        )}
      </section>
      <p className="text-[10px] leading-relaxed text-slate-400">
        {isAdmin && (
          <Link
            href="/supply-chain?benchmark=1"
            className="ml-3 text-cyan-700 underline"
          >
            管理员地图规模自测
          </Link>
        )}
      </p>
    </div>
  );
}
