"use client";

import { useEffect, useRef, useState } from "react";
import {
  Map,
  Marker,
  NavigationControl,
  setWorkerCount,
  setWorkerUrl,
  type GeoJSONSource,
} from "maplibre-gl";
import { MapLibreOverlay } from "@deck.gl/maplibre";
import {
  PathLayer,
  PolygonLayer,
  ScatterplotLayer,
  TextLayer,
} from "@deck.gl/layers";
import "maplibre-gl/dist/maplibre-gl.css";
import type { NetworkData, NetworkSite, NetworkShipment } from "@/lib/network";

type MapProps = {
  data: NetworkData;
  selectedSite: string | null;
  selectedShipment: string | null;
  onSite: (id: string) => void;
  onShipment: (id: string) => void;
  layers: {
    risk: boolean;
    plans: boolean;
    tracks: boolean;
    dependencies: boolean;
  };
  forceFallback?: boolean;
};
export default function NetworkMap(props: MapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Map | null>(null);
  const overlay = useRef<MapLibreOverlay | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (props.forceFallback) {
      setError("已启用无 WebGL 检查模式；站点、运输批次和订单列表仍可使用。");
      return;
    }
    if (!container.current) return;
    let active = true;
    const clusterMarkers = new globalThis.Map<number, Marker>();
    try {
      setWorkerUrl("/maps/maplibre-gl-worker.mjs");
      setWorkerCount(1);
      const instance = new Map({
        container: container.current,
        center: [116.4, 29.6],
        zoom: 4.1,
        minZoom: 1,
        maxZoom: 10,
        attributionControl: false,
        renderWorldCopies: false,
        style: {
          version: 8,
          sources: { land: { type: "geojson", data: "/maps/land.geojson" } },
          layers: [
            {
              id: "ocean",
              type: "background",
              paint: { "background-color": "#08121e" },
            },
            {
              id: "land",
              type: "fill",
              source: "land",
              paint: { "fill-color": "#15283b", "fill-opacity": 1 },
            },
            {
              id: "coastline",
              type: "line",
              source: "land",
              paint: { "line-color": "#31506b", "line-width": 0.7 },
            },
          ],
        },
      });
      map.current = instance;
      (window as unknown as { __supplyguardMap?: Map }).__supplyguardMap =
        instance;
      instance.addControl(
        new NavigationControl({ showCompass: false }),
        "bottom-right",
      );
      instance.on("error", (event) => {
        if (active)
          setError(
            `地图资源或 WebGL 加载失败，仍可使用列表。${event.error?.message || ""}`,
          );
      });
      instance.on("webglcontextlost", () => {
        if (active) setError("WebGL 上下文中断，请刷新或继续使用列表。");
      });
      instance.on("load", async () => {
        if (!active) return;
        instance.addSource("sites", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
          cluster: true,
          clusterRadius: 38,
          clusterMaxZoom: 5,
        });
        instance.addSource("dependencies", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        instance.addLayer({
          id: "dependency-lines",
          type: "line",
          source: "dependencies",
          paint: {
            "line-color": "#d990c8",
            "line-width": 1.5,
            "line-opacity": 0.65,
            "line-dasharray": [2, 3],
          },
        });
        instance.addLayer({
          id: "site-clusters",
          type: "circle",
          source: "sites",
          filter: ["has", "point_count"],
          paint: {
            "circle-color": "#155e75",
            "circle-radius": [
              "step",
              ["get", "point_count"],
              15,
              10,
              20,
              100,
              26,
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#67e8f9",
          },
        });
        instance.addLayer({
          id: "site-nodes",
          type: "circle",
          source: "sites",
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": [
              "case",
              [">", ["get", "risk_count"], 0],
              "#fb7185",
              "#67e8f9",
            ],
            "circle-radius": 6,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#082f49",
          },
        });
        instance.on("render", () => {
          const visible = new Set<number>();
          for (const feature of instance.queryRenderedFeatures({
            layers: ["site-clusters"],
          })) {
            if (feature.geometry.type !== "Point") continue;
            const id = Number(feature.properties?.cluster_id);
            visible.add(id);
            if (!clusterMarkers.has(id)) {
              const label = document.createElement("span");
              label.textContent = String(feature.properties?.point_count);
              Object.assign(label.style, {
                color: "#cffafe",
                fontSize: "12px",
                fontWeight: "700",
                pointerEvents: "none",
              });
              clusterMarkers.set(
                id,
                new Marker({ element: label })
                  .setLngLat(feature.geometry.coordinates as [number, number])
                  .addTo(instance),
              );
            }
          }
          for (const [id, marker] of clusterMarkers) {
            if (!visible.has(id)) {
              marker.remove();
              clusterMarkers.delete(id);
            }
          }
        });
        instance.on("click", "site-clusters", async (event) => {
          const feature = event.features?.[0];
          if (!feature || feature.geometry.type !== "Point") return;
          const zoom = await (
            instance.getSource("sites") as GeoJSONSource
          ).getClusterExpansionZoom(Number(feature.properties?.cluster_id));
          instance.easeTo({
            center: feature.geometry.coordinates as [number, number],
            zoom: Math.min(zoom + 0.2, 9),
            duration: 450,
          });
        });
        instance.on("click", "site-nodes", (event) => {
          const id = event.features?.[0]?.properties?.id;
          if (id) latest.current.onSite(String(id));
        });
        for (const id of ["site-clusters", "site-nodes"]) {
          instance.on("mouseenter", id, () => {
            instance.getCanvas().style.cursor = "pointer";
          });
          instance.on("mouseleave", id, () => {
            instance.getCanvas().style.cursor = "";
          });
        }
        await document.fonts.load('12px "SupplyGuardMap"');
        if (!active) return;
        const deck = new MapLibreOverlay({
          interleaved: false,
          layers: [],
          onError: (e) => {
            if (active) setError(`地图绘制失败，仍可使用列表。${e.message}`);
          },
        });
        instance.addControl(deck);
        overlay.current = deck;
        setReady(true);
      });
    } catch (e) {
      setError(
        `当前浏览器无法使用 WebGL，仍可使用列表。${(e as Error).message}`,
      );
    }
    return () => {
      active = false;
      setReady(false);
      overlay.current = null;
      for (const marker of clusterMarkers.values()) marker.remove();
      map.current?.remove();
      map.current = null;
      delete (window as unknown as { __supplyguardMap?: Map }).__supplyguardMap;
    };
  }, [props.forceFallback]);
  useEffect(() => {
    const instance = map.current,
      deck = overlay.current;
    if (!ready || !instance || !deck) return;
    const { data, layers, selectedShipment, selectedSite } = props;
    (instance.getSource("sites") as GeoJSONSource).setData({
      type: "FeatureCollection",
      features: data.sites.map((s) => ({
        type: "Feature",
        properties: {
          id: s.id,
          name: s.name,
          risk_count: layers.risk ? s.risk_event_ids.length : 0,
        },
        geometry: { type: "Point", coordinates: [s.longitude, s.latitude] },
      })),
    });
    const lookup = new globalThis.Map(data.sites.map((s) => [s.id, s]));
    const dependencies = new globalThis.Map<
      string,
      {
        type: "Feature";
        properties: Record<string, never>;
        geometry: { type: "LineString"; coordinates: number[][] };
      }
    >();
    if (layers.dependencies)
      data.orders
        .filter((o) => o.risk_event_ids.length)
        .forEach((o) =>
          o.dependency_paths.forEach((p) => {
            const source = lookup.get(p.nodes[0].site_id || ""),
              dest = lookup.get(o.destination_site_id);
            if (source && dest && source.id !== dest.id)
              dependencies.set(`${source.id}-${dest.id}`, {
                type: "Feature",
                properties: {},
                geometry: {
                  type: "LineString",
                  coordinates: [
                    [source.longitude, source.latitude],
                    [dest.longitude, dest.latitude],
                  ],
                },
              });
          }),
        );
    (instance.getSource("dependencies") as GeoJSONSource).setData({
      type: "FeatureCollection",
      features: [...dependencies.values()],
    });
    const positions = data.shipments.filter((s) => s.position);
    const selected = data.sites.filter((s) => s.id === selectedSite);
    deck.setProps({
      layers: [
        new PolygonLayer({
          id: "risk-areas",
          data: layers.risk ? data.risk_areas : [],
          getPolygon: (d) => d.polygon,
          getFillColor: [244, 63, 94, 35],
          stroked: true,
          getLineColor: [251, 113, 133, 170],
          getLineWidth: 1,
          lineWidthUnits: "pixels",
        }),
        new PathLayer<NetworkShipment>({
          id: "planned-routes",
          data: layers.plans ? data.shipments : [],
          getPath: (d) => d.route,
          getColor: (d) =>
            !selectedShipment || selectedShipment === d.id
              ? [56, 189, 248, 125]
              : [71, 85, 105, 70],
          widthMinPixels: 1.7,
          pickable: true,
          onClick: (info) => {
            if (info.object) latest.current.onShipment(info.object.id);
          },
        }),
        new PathLayer<NetworkShipment>({
          id: "replayed-tracks",
          data: layers.tracks ? data.shipments : [],
          getPath: (d) =>
            d.trace.map((p) => [p.longitude, p.latitude] as [number, number]),
          getColor: (d) =>
            !selectedShipment || selectedShipment === d.id
              ? [251, 191, 36, 235]
              : [100, 116, 139, 90],
          widthMinPixels: 2.6,
        }),
        new ScatterplotLayer<NetworkShipment>({
          id: "shipment-positions",
          data: positions,
          getPosition: (d) => [d.position!.longitude, d.position!.latitude],
          getRadius: 5,
          radiusUnits: "pixels",
          getFillColor: (d) =>
            d.id === selectedShipment
              ? [190, 242, 100, 255]
              : [248, 250, 252, 245],
          stroked: true,
          getLineColor: [14, 116, 144, 255],
          lineWidthMinPixels: 2,
          pickable: true,
          onClick: (info) => {
            if (info.object) latest.current.onShipment(info.object.id);
          },
        }),
        new ScatterplotLayer<NetworkSite>({
          id: "selected-site",
          data: selected,
          getPosition: (d) => [d.longitude, d.latitude],
          getRadius: 12,
          radiusUnits: "pixels",
          filled: false,
          stroked: true,
          getLineColor: [190, 242, 100, 255],
          lineWidthMinPixels: 2,
        }),
        new TextLayer<NetworkSite>({
          id: "site-labels",
          data: data.sites.filter(
            (s) =>
              s.id === selectedSite ||
              (layers.risk && s.risk_event_ids.length > 0),
          ),
          getPosition: (d) => [d.longitude, d.latitude],
          getText: (d) => d.name,
          getColor: [203, 213, 225, 255],
          getSize: 12,
          getPixelOffset: [0, -16],
          fontFamily: "SupplyGuardMap",
          characterSet: "auto",
          fontSettings: { sdf: false },
          background: true,
          getBackgroundColor: [8, 18, 30, 210],
          backgroundPadding: [4, 2],
        }),
      ],
    });
  }, [
    props.data,
    props.layers,
    props.selectedShipment,
    props.selectedSite,
    ready,
  ]);
  useEffect(() => {
    const site = props.data.sites.find((s) => s.id === props.selectedSite);
    if (ready && site)
      map.current?.flyTo({
        center: [site.longitude, site.latitude],
        zoom: Math.max(map.current.getZoom(), 6),
        duration: 650,
      });
  }, [props.selectedSite, ready]);
  return (
    <div
      className="relative h-full min-h-[430px] overflow-hidden rounded-2xl bg-[#08121e]"
      data-testid="network-map"
      data-map-ready={ready && !error ? "true" : "false"}
      data-map-sites={props.data.sites.length}
      data-map-routes={props.data.shipments.length}
    >
      <div
        ref={container}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
        }}
      />
      {!ready && !error && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
          正在加载本地地图资源…
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="absolute left-5 right-5 top-5 rounded-xl border border-amber-400/30 bg-slate-900 p-4 text-sm text-amber-200"
          data-testid="map-fallback"
        >
          {error}
        </div>
      )}
      <div className="absolute left-4 top-4 rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-2 text-[10px] text-slate-400">
        WGS84 · 本地底图 · 模拟业务网络
      </div>
      <div className="absolute right-4 top-4 flex gap-2">
        <button
          aria-label="聚焦制造区域"
          className="rounded-lg border border-slate-600 bg-slate-900/90 px-3 py-2 text-xs text-slate-300"
          onClick={() =>
            map.current?.flyTo({
              center: [116.4, 29.6],
              zoom: 4.1,
              duration: 500,
            })
          }
        >
          区域
        </button>
        <button
          aria-label="查看全部站点"
          className="rounded-lg border border-slate-600 bg-slate-900/90 px-3 py-2 text-xs text-slate-300"
          onClick={() => {
            const sites = props.data.sites;
            if (!sites.length) return;
            map.current?.fitBounds(
              [
                [
                  Math.min(...sites.map((s) => s.longitude)),
                  Math.min(...sites.map((s) => s.latitude)),
                ],
                [
                  Math.max(...sites.map((s) => s.longitude)),
                  Math.max(...sites.map((s) => s.latitude)),
                ],
              ],
              { padding: 65, maxZoom: 6, duration: 600 },
            );
          }}
        >
          全网
        </button>
      </div>
      <div className="absolute bottom-9 left-4 flex max-w-[80%] flex-wrap gap-x-4 gap-y-2 rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-2 text-[10px] text-slate-300">
        <span>◉ 风险站点 / 演示覆盖区</span>
        <span className="text-sky-300">━ 计划路线</span>
        <span className="text-amber-300">━ 已回放轨迹</span>
        <span className="text-fuchsia-300">┄ 场景依赖关联</span>
        <span>● 模拟位置</span>
      </div>
      <a
        href="https://www.naturalearthdata.com/"
        target="_blank"
        rel="noreferrer"
        className="absolute bottom-2 left-4 text-[9px] text-slate-500"
      >
        底图：Natural Earth（Public Domain）· 地理概览，非道路导航
      </a>
    </div>
  );
}
