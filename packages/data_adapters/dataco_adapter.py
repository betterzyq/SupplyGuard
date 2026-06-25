"""DataCo Supply Chain dataset adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from packages.data_adapters.base import BaseDatasetAdapter
from packages.data_adapters.schema import DatasetProfile, NormalizedDataset, RawDataset, ValidationReport, empty_tables, empty_normalized
from packages.data_adapters.utils import (
    ensure_columns,
    find_column,
    parse_date_series,
    read_tabular,
    scan_dataset_files,
    severity_from_delay,
    slug_code,
    stable_id,
    to_iso_date,
)

SOURCE = "dataco"


class DataCoAdapter(BaseDatasetAdapter):
    dataset_name = SOURCE

    def detect(self, file_paths: list[Path]) -> bool:
        for path in file_paths:
            if "dataco" in str(path).lower() and path.suffix.lower() == ".csv":
                return True
        return False

    def _primary_file(self) -> Path:
        for path in self.file_paths:
            if path.suffix.lower() == ".csv":
                return path
        raise FileNotFoundError("No DataCo CSV found")

    def profile(self) -> DatasetProfile:
        path = self._primary_file()
        df = read_tabular(path, nrows=100)
        return DatasetProfile(
            dataset_name=self.dataset_name,
            file_paths=[str(p) for p in self.file_paths],
            row_counts={"primary": len(read_tabular(path)) if self.limit is None else min(self.limit, 5000)},
            columns={"primary": list(df.columns)},
            notes=["Maps orders, customers, products, deliveries, risk_events"],
        )

    def load(self) -> RawDataset:
        path = self._primary_file()
        df = read_tabular(path, nrows=self.limit)
        self._raw = RawDataset(dataset_name=self.dataset_name, frames={"orders_raw": df})
        return self._raw

    def transform(self) -> NormalizedDataset:
        raw = self.load()
        df = raw.frames["orders_raw"]
        tables = empty_tables()

        col_order_id = find_column(df, ["Order Id", "order id"])
        col_product = find_column(df, ["Product Name", "product name"])
        col_product_card = find_column(df, ["Product Card Id", "product card id"])
        col_customer_id = find_column(df, ["Customer Id", "customer id"])
        col_customer_country = find_column(df, ["Customer Country", "customer country"])
        col_customer_city = find_column(df, ["Customer City", "customer city"])
        col_category = find_column(df, ["Category Name", "category name"])
        col_order_date = find_column(df, ["order date (DateOrders)", "order date"])
        col_ship_date = find_column(df, ["shipping date (DateOrders)", "shipping date"])
        col_qty = find_column(df, ["Order Item Quantity", "order item quantity"])
        col_status = find_column(df, ["Order Status", "order status"])
        col_delivery_status = find_column(df, ["Delivery Status", "delivery status"])
        col_late_risk = find_column(df, ["Late_delivery_risk", "late delivery risk"])
        col_ship_mode = find_column(df, ["Shipping Mode", "shipping mode"])
        col_order_country = find_column(df, ["Order Country", "order country"])
        col_days_real = find_column(df, ["Days for shipping (real)", "days for shipping real"])
        col_days_sched = find_column(df, ["Days for shipment (scheduled)", "days for shipment scheduled"])
        col_region = find_column(df, ["Order Region", "order region"])
        col_customer_fname = find_column(df, ["Customer Fname", "customer fname"])
        col_customer_lname = find_column(df, ["Customer Lname", "customer lname"])
        col_item_id = find_column(df, ["Order Item Id", "order item id"])

        # Products
        if col_product:
            prod_cols = [col_product]
            if col_product_card:
                prod_cols.append(col_product_card)
            if col_category:
                prod_cols.append(col_category)
            prod_df = df[prod_cols].drop_duplicates()
            products = []
            for _, row in prod_df.iterrows():
                pname = str(row[col_product]).strip()
                pcode = str(row[col_product_card]) if col_product_card else slug_code(pname)
                pid = stable_id("DC-PRD", pcode, pname)
                products.append(
                    {
                        "product_id": pid,
                        "product_code": f"DC-{pcode}",
                        "product_name": pname,
                        "category": str(row[col_category]) if col_category and pd.notna(row[col_category]) else None,
                        "source_dataset": SOURCE,
                    }
                )
            tables["products"] = pd.DataFrame(products)

        product_id_by_name: dict[str, str] = {}
        if len(tables["products"]):
            for _, r in tables["products"].iterrows():
                product_id_by_name[str(r["product_name"]).strip().lower()] = r["product_id"]

        # Customers
        if col_customer_id:
            cust_df = df[[c for c in [col_customer_id, col_customer_fname, col_customer_lname, col_customer_country, col_region] if c]].drop_duplicates(subset=[col_customer_id])
            customers = []
            for _, row in cust_df.iterrows():
                cid = stable_id("DC-CUS", row[col_customer_id])
                name_parts = []
                if col_customer_fname and pd.notna(row.get(col_customer_fname)):
                    name_parts.append(str(row[col_customer_fname]))
                if col_customer_lname and pd.notna(row.get(col_customer_lname)):
                    name_parts.append(str(row[col_customer_lname]))
                cname = " ".join(name_parts) or f"Customer {row[col_customer_id]}"
                customers.append(
                    {
                        "customer_id": cid,
                        "customer_name": cname,
                        "country": str(row[col_customer_country]) if col_customer_country and pd.notna(row.get(col_customer_country)) else None,
                        "region": str(row[col_region]) if col_region and pd.notna(row.get(col_region)) else None,
                        "tier": "standard",
                        "source_dataset": SOURCE,
                    }
                )
            tables["customers"] = pd.DataFrame(customers)

        customer_id_by_ext: dict[str, str] = {}
        if len(tables["customers"]) and col_customer_id:
            for _, row in df[[col_customer_id]].drop_duplicates().iterrows():
                customer_id_by_ext[str(row[col_customer_id])] = stable_id("DC-CUS", row[col_customer_id])

        # Orders + deliveries + risk events
        orders, deliveries, risks = [], [], []
        product_order_edges, order_customer_edges = [], []

        if col_order_id:
            group_cols = [col_order_id]
            if col_product:
                group_cols.append(col_product)
            grouped = df.groupby(group_cols, dropna=False)

            for key, grp in grouped:
                if not isinstance(key, tuple):
                    key = (key,)
                order_ext = key[0]
                first = grp.iloc[0]
                pname = str(first[col_product]).strip() if col_product else "Unknown Product"
                item_key = (
                    str(first[col_item_id])
                    if col_item_id and pd.notna(first.get(col_item_id))
                    else pname
                )
                oid = stable_id("DC-ORD", order_ext, item_key)
                order_no = f"DC-{order_ext}"
                pid = product_id_by_name.get(pname.lower())
                cid = customer_id_by_ext.get(str(first[col_customer_id])) if col_customer_id else None

                qty = int(grp[col_qty].sum()) if col_qty and col_qty in grp else len(grp)
                order_date = to_iso_date(first[col_order_date]) if col_order_date else None
                ship_date = to_iso_date(first[col_ship_date]) if col_ship_date else None

                days_real = pd.to_numeric(first[col_days_real], errors="coerce") if col_days_real else None
                days_sched = pd.to_numeric(first[col_days_sched], errors="coerce") if col_days_sched else None
                delay_days = None
                if days_real is not None and days_sched is not None and pd.notna(days_real) and pd.notna(days_sched):
                    delay_days = int(days_real - days_sched)

                orders.append(
                    {
                        "order_id": oid,
                        "order_no": order_no,
                        "supplier_id": None,
                        "product_id": pid,
                        "customer_id": cid,
                        "order_date": order_date,
                        "expected_delivery_date": order_date,
                        "actual_delivery_date": ship_date,
                        "quantity": qty,
                        "order_status": str(first[col_status]) if col_status and pd.notna(first.get(col_status)) else "unknown",
                        "source_dataset": SOURCE,
                    }
                )

                if pid:
                    product_order_edges.append(
                        {
                            "product_id": pid,
                            "order_id": oid,
                            "relationship_type": "ORDERED_IN",
                            "source_dataset": SOURCE,
                        }
                    )
                if cid:
                    order_customer_edges.append(
                        {
                            "order_id": oid,
                            "customer_id": cid,
                            "relationship_type": "FOR_CUSTOMER",
                            "source_dataset": SOURCE,
                        }
                    )

                delivery_status = str(first[col_delivery_status]).lower() if col_delivery_status and pd.notna(first.get(col_delivery_status)) else ""
                late_flag = False
                if col_late_risk and pd.notna(first.get(col_late_risk)):
                    late_flag = int(pd.to_numeric(first[col_late_risk], errors="coerce") or 0) == 1
                if "late" in delivery_status or "delay" in delivery_status:
                    late_flag = True

                deliveries.append(
                    {
                        "delivery_id": stable_id("DC-DLV", oid),
                        "order_id": oid,
                        "supplier_id": None,
                        "shipment_mode": str(first[col_ship_mode]) if col_ship_mode and pd.notna(first.get(col_ship_mode)) else None,
                        "origin_country": str(first[col_order_country]) if col_order_country and pd.notna(first.get(col_order_country)) else None,
                        "destination_country": str(first[col_customer_country]) if col_customer_country and pd.notna(first.get(col_customer_country)) else None,
                        "planned_date": order_date,
                        "actual_date": ship_date,
                        "delay_days": delay_days,
                        "delay_reason": delivery_status or None,
                        "delivery_status": str(first[col_delivery_status]) if col_delivery_status else None,
                        "freight_cost": None,
                        "source_dataset": SOURCE,
                    }
                )

                if late_flag:
                    sev = severity_from_delay(delay_days if delay_days is not None else 1)
                    risks.append(
                        {
                            "risk_event_id": stable_id("DC-RISK", oid, "late"),
                            "supplier_id": None,
                            "country": str(first[col_order_country]) if col_order_country else None,
                            "event_type": "delivery_delay",
                            "severity": sev,
                            "title": f"Late delivery risk for order {order_no}",
                            "description": f"Delivery status={delivery_status or 'late'}; delay_days={delay_days}",
                            "source": "dataco_late_delivery_risk",
                            "detected_at": ship_date or order_date,
                            "source_dataset": SOURCE,
                        }
                    )

        tables["orders"] = pd.DataFrame(orders)
        tables["deliveries"] = pd.DataFrame(deliveries)
        tables["risk_events"] = pd.DataFrame(risks)
        tables["product_order_edges"] = pd.DataFrame(product_order_edges)
        tables["order_customer_edges"] = pd.DataFrame(order_customer_edges)

        for name, cols in tables.items():
            if isinstance(tables[name], pd.DataFrame) and len(tables[name]):
                tables[name] = ensure_columns(tables[name], tables[name].columns.tolist())

        self._normalized = NormalizedDataset(dataset_name=self.dataset_name, tables=tables)
        return self._normalized

    def validate(self) -> ValidationReport:
        report = super().validate()
        n = self._normalized
        if n and len(n.table("orders")) == 0:
            report.errors.append("No orders produced from DataCo")
            report.passed = False
        if n and len(n.table("customers")) == 0:
            report.warnings.append("No customers produced from DataCo")
        return report


def build_dataco_adapter(external_root: Path, limit: int | None = None) -> DataCoAdapter | None:
    root = external_root / "dataco"
    files = scan_dataset_files(root)
    adapter = DataCoAdapter(external_root, limit=limit)
    if adapter.detect(files):
        adapter.bind_files(files)
        return adapter
    return None
