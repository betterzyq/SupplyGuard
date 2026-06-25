"""Neo4j graph schema constants."""

NODE_LABELS = (
    "Supplier",
    "Material",
    "Product",
    "Customer",
    "Order",
    "RiskEvent",
    "DeliveryEvent",
    "QualityIssue",
)

RELATIONSHIP_TYPES = (
    "SUPPLIES",
    "USED_IN",
    "ORDERED_IN",
    "FOR_CUSTOMER",
    "HAS_RISK_EVENT",
    "HAS_DELIVERY_EVENT",
    "HAS_QUALITY_ISSUE",
    "ALTERNATIVE_TO",
)

QUERY_TYPES = (
    "supplier_impact",
    "product_dependency",
    "supplier_alternatives",
    "delivery_delay_impact",
    "quality_issue_trace",
    "customer_order_dependency",
)

CONSTRAINTS = [
    "CREATE CONSTRAINT supplier_unique IF NOT EXISTS FOR (n:Supplier) REQUIRE (n.tenant_id, n.code) IS UNIQUE",
    "CREATE CONSTRAINT material_unique IF NOT EXISTS FOR (n:Material) REQUIRE (n.tenant_id, n.code) IS UNIQUE",
    "CREATE CONSTRAINT product_unique IF NOT EXISTS FOR (n:Product) REQUIRE (n.tenant_id, n.code) IS UNIQUE",
    "CREATE CONSTRAINT customer_unique IF NOT EXISTS FOR (n:Customer) REQUIRE (n.tenant_id, n.code) IS UNIQUE",
    "CREATE CONSTRAINT order_unique IF NOT EXISTS FOR (n:Order) REQUIRE (n.tenant_id, n.code) IS UNIQUE",
    "CREATE CONSTRAINT risk_event_unique IF NOT EXISTS FOR (n:RiskEvent) REQUIRE (n.tenant_id, n.id) IS UNIQUE",
    "CREATE CONSTRAINT delivery_event_unique IF NOT EXISTS FOR (n:DeliveryEvent) REQUIRE (n.tenant_id, n.id) IS UNIQUE",
    "CREATE CONSTRAINT quality_issue_unique IF NOT EXISTS FOR (n:QualityIssue) REQUIRE (n.tenant_id, n.id) IS UNIQUE",
]
