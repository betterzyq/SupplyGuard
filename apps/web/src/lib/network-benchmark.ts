import type { NetworkData, NetworkSite, NetworkShipment } from "./network";
/** Geometry-only test workload; never used as customer KPI evidence. */
export function benchmarkNetwork(base: NetworkData): NetworkData {
  let state = 20261017;
  const random = () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
  const sites: NetworkSite[] = Array.from({ length: 1000 }, (_, i) => ({
    id: `BENCH-SITE-${i}`,
    name: `测试站点 ${i}`,
    kind: "supplier",
    country: "SYNTHETIC",
    longitude: 102 + random() * 22,
    latitude: 20 + random() * 18,
    risk_event_ids: [],
  }));
  const template = base.shipments[0];
  if (!template) return { ...base, sites, shipments: [] };
  const shipments: NetworkShipment[] = Array.from({ length: 2000 }, (_, i) => {
    const a = sites[i % sites.length],
      b = sites[(i * 17 + 31) % sites.length];
    return {
      ...template,
      id: `BENCH-ROUTE-${i}`,
      origin_site_id: a.id,
      destination_site_id: b.id,
      route: [
        [a.longitude, a.latitude],
        [(a.longitude + b.longitude) / 2, (a.latitude + b.latitude) / 2 + 0.2],
        [b.longitude, b.latitude],
      ],
      trace: [],
      position: null,
      order_ids: [],
    };
  });
  return { ...base, sites, shipments, risk_areas: [], risk_events: [] };
}
