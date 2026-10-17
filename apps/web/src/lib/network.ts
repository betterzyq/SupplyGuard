import { create } from "zustand";
import { apiClient, type UserInfo } from "./api";
import type { BusinessOrder, BusinessEvent, Scenario } from "./business";

export interface ReplayPoint {
  longitude: number;
  latitude: number;
  at: string;
}
export interface NetworkSite {
  id: string;
  name: string;
  kind: string;
  country: string;
  longitude: number;
  latitude: number;
  risk_event_ids: string[];
}
export interface DependencyNode {
  id: string;
  name: string;
  type: string;
  site_id?: string;
}
export interface NetworkOrder extends Omit<BusinessOrder, "severity"> {
  supplier_id: string;
  product_id: string;
  destination_site_id: string;
  severity: "medium" | "high" | "critical" | null;
  shipment_ids: string[];
  dependency_paths: { nodes: DependencyNode[]; relationships: string[] }[];
}
export interface NetworkShipment {
  id: string;
  name: string;
  order_ids: string[];
  origin_site_id: string;
  destination_site_id: string;
  mode: string;
  route: [number, number][];
  trace: ReplayPoint[];
  position: ReplayPoint | null;
  planned_eta: string;
  eta: string;
  eta_source: string;
  eta_reason: string;
  position_source: string;
  delay_hours: number;
  carrier: string;
  eta_updates: { observed_at: string; eta: string; reason: string }[];
  milestones: {
    name: string;
    planned_at: string;
    observed_at: string | null;
  }[];
}
export interface NetworkData {
  tenant_id: string;
  source_type: "synthetic";
  dataset_version: string;
  coordinate_system: "WGS84";
  as_of: string;
  timeline: { start_at: string; end_at: string };
  scenario: Scenario;
  scenarios: Scenario[];
  suppliers: { id: string; name: string; site_id: string; tier: number }[];
  sites: NetworkSite[];
  orders: NetworkOrder[];
  shipments: NetworkShipment[];
  risk_events: (BusinessEvent & { site_ids: string[] })[];
  risk_areas: {
    event_id: string;
    site_id: string;
    severity: string;
    polygon: [number, number][];
  }[];
  metrics: {
    exposure_amount_cny: string;
    at_risk_orders: number;
    visible_orders: number;
    visible_sites: number;
    visible_shipments: number;
    active_risk_events: number;
  };
  notice: string;
}
export interface NetworkFilters {
  atTime?: string | null;
  supplierId?: string;
  mode?: string;
  search?: string;
  riskOnly?: boolean;
}
export const useNetworkFilters = create<{
  supplierId: string;
  mode: string;
  search: string;
  riskOnly: boolean;
  setSupplierId: (value: string) => void;
  setMode: (value: string) => void;
  setSearch: (value: string) => void;
  setRiskOnly: (value: boolean) => void;
  reset: () => void;
}>((set) => ({
  supplierId: "",
  mode: "",
  search: "",
  riskOnly: false,
  setSupplierId: (supplierId) => set({ supplierId }),
  setMode: (mode) => set({ mode }),
  setSearch: (search) => set({ search }),
  setRiskOnly: (riskOnly) => set({ riskOnly }),
  reset: () => set({ supplierId: "", mode: "", search: "", riskOnly: false }),
}));

const severityRank: Record<string, number> = {
  medium: 1,
  high: 2,
  critical: 3,
};
const prefix = "sg-network-v2:";
export const modeLabels: Record<string, string> = {
  ocean: "海运",
  road: "公路",
  rail: "铁路",
  air: "空运",
};
export const siteLabels: Record<string, string> = {
  factory: "制造中心",
  warehouse: "仓库",
  port: "港口",
  supplier: "供应站点",
};
function cacheKey(user: UserInfo, scenario: string) {
  return `${prefix}${user.tenant_id}:${user.id}:${scenario}`;
}
export function clearNetworkCache() {
  if (typeof window === "undefined") return;
  for (const key of Object.keys(localStorage))
    if (key.startsWith(prefix)) localStorage.removeItem(key);
}
export async function getNetworkSnapshot(
  user: UserInfo,
  scenario: string,
): Promise<NetworkData> {
  const key = cacheKey(user, scenario);
  if (!navigator.onLine) {
    const cached = localStorage.getItem(key);
    if (!cached)
      throw new Error("此场景尚未缓存，请联网打开一次后再离线演示。");
    const data = JSON.parse(cached) as NetworkData;
    if (
      data.source_type !== "synthetic" ||
      data.tenant_id !== user.tenant_id ||
      data.scenario.id !== scenario ||
      data.coordinate_system !== "WGS84"
    )
      throw new Error("离线场景不匹配，请重新联网准备。");
    return data;
  }
  const { data } = await apiClient.get<NetworkData>("/business/network", {
    params: { scenario_id: scenario },
    timeout: 10000,
  });
  if (data.source_type === "synthetic" && data.tenant_id === user.tenant_id) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
    } catch {
      /* Full storage must not break online views. */
    }
  }
  return data;
}
export function clipReplay(points: ReplayPoint[], at: number): ReplayPoint[] {
  const result = points
    .filter((p) => Date.parse(p.at) <= at)
    .map((p) => ({ ...p }));
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1],
      b = points[i],
      left = Date.parse(a.at),
      right = Date.parse(b.at);
    if (left < at && at < right) {
      const f = (at - left) / (right - left);
      result.push({
        longitude: a.longitude + (b.longitude - a.longitude) * f,
        latitude: a.latitude + (b.latitude - a.latitude) * f,
        at: new Date(at).toISOString(),
      });
      break;
    }
  }
  return result;
}
export function projectNetwork(
  source: NetworkData,
  filters: NetworkFilters,
): NetworkData {
  const at = Math.max(
    Date.parse(source.timeline.start_at),
    Math.min(
      Date.parse(filters.atTime || source.timeline.end_at),
      Date.parse(source.timeline.end_at),
    ),
  );
  const events = source.risk_events.filter(
    (e) => Date.parse(e.detected_at) <= at,
  );
  const orders = source.orders
    .map((o) => {
      const risks = events.filter((e) => e.affected_order_ids.includes(o.id));
      return {
        ...o,
        risk_event_ids: risks.map((e) => e.id),
        severity: risks.length
          ? (risks.reduce((a, b) =>
              severityRank[a.severity] > severityRank[b.severity] ? a : b,
            ).severity as NetworkOrder["severity"])
          : null,
      };
    })
    .filter((o) => {
      const search = [
        o.id,
        o.customer,
        o.supplier_name,
        o.product_name,
        ...o.shipment_ids,
      ]
        .join(" ")
        .toLowerCase();
      return (
        (!filters.supplierId || o.supplier_id === filters.supplierId) &&
        (!filters.mode ||
          source.shipments.some(
            (s) => o.shipment_ids.includes(s.id) && s.mode === filters.mode,
          )) &&
        search.includes((filters.search || "").trim().toLowerCase()) &&
        (!filters.riskOnly || !!o.risk_event_ids.length)
      );
    });
  const orderIds = new Set(orders.map((o) => o.id));
  const visibleEvents = events.filter((e) =>
    e.affected_order_ids.some((id) => orderIds.has(id)),
  );
  const shipments = source.shipments
    .filter((s) => s.order_ids.some((id) => orderIds.has(id)))
    .map((s) => {
      const trace = clipReplay(s.trace, at);
      const updates = s.eta_updates
        .filter((u) => Date.parse(u.observed_at) <= at)
        .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
      const update = updates[updates.length - 1];
      const eta = update?.eta || s.planned_eta;
      return {
        ...s,
        order_ids: s.order_ids.filter((id) => orderIds.has(id)),
        trace,
        position: trace[trace.length - 1] || null,
        eta,
        eta_reason: update?.reason || "演示运输计划",
        delay_hours: Math.max(
          0,
          Math.round((Date.parse(eta) - Date.parse(s.planned_eta)) / 360000) /
            10,
        ),
        eta_updates: updates,
        milestones: s.milestones.map((m) => ({
          ...m,
          observed_at:
            m.observed_at && Date.parse(m.observed_at) <= at
              ? m.observed_at
              : null,
        })),
      };
    });
  const siteIds = new Set(visibleEvents.flatMap((e) => e.site_ids));
  orders.forEach((o) => {
    siteIds.add(o.destination_site_id);
    const supplier = source.suppliers.find((s) => s.id === o.supplier_id);
    if (supplier) siteIds.add(supplier.site_id);
    o.dependency_paths.forEach((p) => {
      if (p.nodes[0].site_id) siteIds.add(p.nodes[0].site_id);
    });
  });
  shipments.forEach((s) => {
    siteIds.add(s.origin_site_id);
    siteIds.add(s.destination_site_id);
  });
  const sites = source.sites
    .filter((s) => siteIds.has(s.id))
    .map((s) => ({
      ...s,
      risk_event_ids: visibleEvents
        .filter((e) => e.site_ids.includes(s.id))
        .map((e) => e.id),
    }));
  const exposed = orders.filter((o) => o.risk_event_ids.length);
  const cents = exposed.reduce((sum, o) => {
    const [a, b = ""] = o.amount_cny.split(".");
    return sum + BigInt(a) * BigInt(100) + BigInt(b.padEnd(2, "0"));
  }, BigInt(0));
  return {
    ...source,
    as_of: new Date(at).toISOString(),
    orders,
    shipments,
    sites,
    risk_events: visibleEvents,
    risk_areas: source.risk_areas.filter((a) =>
      visibleEvents.some((e) => e.id === a.event_id),
    ),
    metrics: {
      exposure_amount_cny: `${cents / BigInt(100)}.${String(cents % BigInt(100)).padStart(2, "0")}`,
      at_risk_orders: exposed.length,
      visible_orders: orders.length,
      visible_sites: sites.length,
      visible_shipments: shipments.length,
      active_risk_events: visibleEvents.length,
    },
  };
}
export async function prepareOfflineDemo(user: UserInfo): Promise<void> {
  if (!navigator.serviceWorker || !navigator.onLine)
    throw new Error("请在联网且支持 Service Worker 的浏览器中准备离线演示。");
  const registration = await navigator.serviceWorker.ready;
  if (!navigator.serviceWorker.controller) {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("离线服务尚未接管页面，请刷新后重试。")),
        7000,
      );
      navigator.serviceWorker.addEventListener(
        "controllerchange",
        () => {
          clearTimeout(timer);
          resolve();
        },
        { once: true },
      );
    });
  }
  await import("@/components/control-tower/DependencyGraph");
  await Promise.all(
    ["port-congestion", "tier2-shutdown", "regional-flood"].map((id) =>
      getNetworkSnapshot(user, id),
    ),
  );
  const cache = await caches.open("supplyguard-public-map-v2");
  for (const pathname of ["/supply-chain", "/tracking"]) {
    const response = await fetch(pathname, {
      headers: { Accept: "text/html" },
    });
    if (!response.ok) throw new Error("离线页面准备失败");
    const html = await response.clone().text();
    await cache.put(pathname, response);
    const document = new DOMParser().parseFromString(html, "text/html");
    const assets = [
      ...document.querySelectorAll("script[src],link[rel=stylesheet]"),
    ]
      .map(
        (node) => node.getAttribute("src") || node.getAttribute("href") || "",
      )
      .filter((url) => url.startsWith("/_next/static/"));
    await Promise.all(
      assets.map(async (url) => {
        const r = await fetch(url);
        if (!r.ok) throw new Error("离线脚本准备失败");
        await cache.put(url, r);
      }),
    );
  }
  await Promise.all(
    [
      "/maps/land.geojson",
      "/maps/maplibre-gl-worker.mjs",
      "/maps/map-ui.woff2",
    ].map(async (url) => {
      const r = await fetch(url);
      if (!r.ok) throw new Error("离线地图资源准备失败");
      await cache.put(url, r);
    }),
  );
  if (!registration.active) throw new Error("离线服务未激活");
}
