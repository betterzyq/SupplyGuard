"""SCMS procurement / delivery dataset adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from packages.data_adapters.base import BaseDatasetAdapter
from packages.data_adapters.schema import DatasetProfile, NormalizedDataset, RawDataset, ValidationReport, empty_tables
from packages.data_adapters.utils import (
    ensure_columns,
    find_column,
    read_tabular,
    scan_dataset_files,
    severity_from_delay,
    slug_code,
    stable_id,
    to_iso_date,
)

SOURCE = "scms"


class ScmsAdapter(BaseDatasetAdapter):
    dataset_name = SOURCE

    def detect(self, file_paths: list[Path]) -> bool:
        for path in file_paths:
            if "scms" in str(path).lower() and path.suffix.lower() in {".csv", ".xlsx", ".xls"}:
                return True
        return False

    def _load_all_frames(self) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for path in self.file_paths:
            key = path.stem
            df = read_tabular(path, nrows=self.limit)
            if key in frames:
                frames[key] = pd.concat([frames[key], df], ignore_index=True)
            else:
                frames[key] = df
        return frames

    def profile(self) -> DatasetProfile:
        frames = self._load_all_frames()
        return DatasetProfile(
            dataset_name=self.dataset_name,
            file_paths=[str(p) for p in self.file_paths],
            row_counts={k: len(v) for k, v in frames.items()},
            columns={k: list(v.columns) for k, v in frames.items()},
            notes=["Maps suppliers, facilities, orders, deliveries, risk_events"],
        )

    def load(self) -> RawDataset:
        frames = self._load_all_frames()
        # Prefer single consolidated frame
        if frames:
            primary = pd.concat(list(frames.values()), ignore_index=True).drop_duplicates()
        else:
            primary = pd.DataFrame()
        self._raw = RawDataset(dataset_name=self.dataset_name, frames={"procurement": primary}, metadata={"files": len(frames)})
        return self._raw

    def transform(self) -> NormalizedDataset:
        raw = self.load()
        df = raw.frames["procurement"]
        tables = empty_tables()

        col_vendor = find_column(df, ["Vendor", "vendor"])
        col_country = find_column(df, ["Country", "country"])
        col_site = find_column(df, ["Manufacturing Site", "manufacturing site"])
        col_po = find_column(df, ["PO / SO #", "PO/SO #", "po / so #"])
        col_ship_mode = find_column(df, ["Shipment Mode", "shipment mode"])
        col_sched = find_column(df, ["Scheduled Delivery Date", "scheduled delivery date"])
        col_delivered = find_column(df, ["Delivered to Client Date", "delivered to client date"])
        col_qty = find_column(df, ["Line Item Quantity", "line item quantity"])
        col_value = find_column(df, ["Line Item Value", "line item value"])
        col_freight = find_column(df, ["Freight Cost (USD)", "freight cost"])
        col_item = find_column(df, ["Item Description", "item description"])
        col_product_group = find_column(df, ["Product Group", "product group"])
        col_po_sent = find_column(df, ["PO Sent to Vendor Date", "po sent to vendor date"])
        col_row_id = find_column(df, ["ID", "id"])

        supplier_id_by_name: dict[str, str] = {}
        facility_id_by_name: dict[str, str] = {}

        # Suppliers
        if col_vendor:
            vendors = df[[c for c in [col_vendor, col_country] if c]].dropna(subset=[col_vendor]).drop_duplicates(subset=[col_vendor])
            suppliers = []
            for _, row in vendors.iterrows():
                vname = str(row[col_vendor]).strip()
                sid = stable_id("SCMS-SUP", vname)
                scode = f"SCMS-{slug_code(vname)[:32]}"
                supplier_id_by_name[vname.lower()] = sid
                suppliers.append(
                    {
                        "supplier_id": sid,
                        "supplier_code": scode,
                        "supplier_name": vname,
                        "country": str(row[col_country]) if col_country and pd.notna(row.get(col_country)) else None,
                        "city": None,
                        "latitude": None,
                        "longitude": None,
                        "tier": 1,
                        "risk_score": 0.0,
                        "status": "active",
                        "source_dataset": SOURCE,
                    }
                )
            tables["suppliers"] = pd.DataFrame(suppliers)

        # Facilities
        if col_site and col_vendor:
            sites = df[[col_site, col_vendor, col_country]].dropna(subset=[col_site]).drop_duplicates(subset=[col_site])
            facilities = []
            for _, row in sites.iterrows():
                site = str(row[col_site]).strip()
                fid = stable_id("SCMS-FAC", site)
                facility_id_by_name[site.lower()] = fid
                vname = str(row[col_vendor]).strip() if pd.notna(row.get(col_vendor)) else ""
                facilities.append(
                    {
                        "facility_id": fid,
                        "supplier_id": supplier_id_by_name.get(vname.lower()),
                        "facility_name": site,
                        "country": str(row[col_country]) if col_country and pd.notna(row.get(col_country)) else None,
                        "city": None,
                        "latitude": None,
                        "longitude": None,
                        "facility_type": "manufacturing",
                        "source_dataset": SOURCE,
                    }
                )
            tables["facilities"] = pd.DataFrame(facilities)

        orders, deliveries, risks = [], [], []
        if col_po or col_row_id:
            iter_df = df.copy()
            for idx, row in iter_df.iterrows():
                po = str(row[col_po]).strip() if col_po and pd.notna(row.get(col_po)) else f"SCMS-ROW-{row[col_row_id] if col_row_id else idx}"
                oid = stable_id("SCMS-ORD", po, str(idx))
                vname = str(row[col_vendor]).strip() if col_vendor and pd.notna(row.get(col_vendor)) else None
                sid = supplier_id_by_name.get(vname.lower()) if vname else None

                sched = to_iso_date(row[col_sched]) if col_sched else None
                delivered = to_iso_date(row[col_delivered]) if col_delivered else None
                po_sent = to_iso_date(row[col_po_sent]) if col_po_sent else None

                delay_days = None
                if sched and delivered:
                    d_sched = pd.to_datetime(sched)
                    d_del = pd.to_datetime(delivered)
                    delay_days = (d_del - d_sched).days

                qty = int(pd.to_numeric(row[col_qty], errors="coerce") or 0) if col_qty else 1
                status = "delivered" if delivered else "open"

                orders.append(
                    {
                        "order_id": oid,
                        "order_no": po if po.startswith("SCMS") else f"SCMS-{po}",
                        "supplier_id": sid,
                        "product_id": None,
                        "customer_id": None,
                        "order_date": po_sent,
                        "expected_delivery_date": sched,
                        "actual_delivery_date": delivered,
                        "quantity": qty,
                        "order_status": status,
                        "source_dataset": SOURCE,
                    }
                )

                freight = pd.to_numeric(row[col_freight], errors="coerce") if col_freight else None
                deliveries.append(
                    {
                        "delivery_id": stable_id("SCMS-DLV", oid),
                        "order_id": oid,
                        "supplier_id": sid,
                        "shipment_mode": str(row[col_ship_mode]) if col_ship_mode and pd.notna(row.get(col_ship_mode)) else None,
                        "origin_country": str(row[col_country]) if col_country and pd.notna(row.get(col_country)) else None,
                        "destination_country": str(row[col_country]) if col_country and pd.notna(row.get(col_country)) else None,
                        "planned_date": sched,
                        "actual_date": delivered,
                        "delay_days": delay_days,
                        "delay_reason": "late_delivery" if delay_days and delay_days > 0 else None,
                        "delivery_status": status,
                        "freight_cost": float(freight) if freight is not None and pd.notna(freight) else None,
                        "source_dataset": SOURCE,
                    }
                )

                if delay_days is not None and delay_days > 0:
                    risks.append(
                        {
                            "risk_event_id": stable_id("SCMS-RISK", oid, "delay"),
                            "supplier_id": sid,
                            "country": str(row[col_country]) if col_country and pd.notna(row.get(col_country)) else None,
                            "event_type": "delivery_delay",
                            "severity": severity_from_delay(delay_days),
                            "title": f"Delivery delay on {po}",
                            "description": (
                                f"Scheduled={sched}, delivered={delivered}, delay_days={delay_days}; "
                                f"item={row[col_item] if col_item else 'n/a'}"
                            ),
                            "source": "scms_delivery_dates",
                            "detected_at": delivered or sched,
                            "source_dataset": SOURCE,
                        }
                    )

        tables["orders"] = pd.DataFrame(orders)
        tables["deliveries"] = pd.DataFrame(deliveries)
        tables["risk_events"] = pd.DataFrame(risks)

        self._normalized = NormalizedDataset(dataset_name=self.dataset_name, tables=tables)
        return self._normalized

    def validate(self) -> ValidationReport:
        report = super().validate()
        if self._normalized and len(self._normalized.table("suppliers")) == 0:
            report.errors.append("No suppliers produced from SCMS")
            report.passed = False
        return report


def build_scms_adapter(external_root: Path, limit: int | None = None) -> ScmsAdapter | None:
    root = external_root / "scms"
    files = scan_dataset_files(root)
    adapter = ScmsAdapter(external_root, limit=limit)
    if adapter.detect(files):
        adapter.bind_files(files)
        return adapter
    return None
