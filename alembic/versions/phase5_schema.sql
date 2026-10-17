-- P5 immutable additive schema snapshot, PostgreSQL16.

CREATE TABLE sg5_events (
	id BIGSERIAL NOT NULL, 
	topic VARCHAR(64) NOT NULL, 
	resource_id VARCHAR(100) NOT NULL, 
	payload JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_events_tenant_id ON sg5_events (tenant_id);

CREATE INDEX ix_sg5_events_topic ON sg5_events (topic);

CREATE TABLE sg5_idempotency (
	operation VARCHAR(80) NOT NULL, 
	key VARCHAR(100) NOT NULL, 
	request_sha256 VARCHAR(64) NOT NULL, 
	response JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, operation, key), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_idempotency_tenant_id ON sg5_idempotency (tenant_id);

CREATE TABLE sg5_activity (
	resource_id VARCHAR(100) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	actor_id UUID NOT NULL, 
	detail JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_activity_resource_id ON sg5_activity (resource_id);

CREATE INDEX ix_sg5_activity_tenant_id ON sg5_activity (tenant_id);

CREATE TABLE sg5_import_batches (
	created_by UUID NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	filename VARCHAR(160) NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	source_sha256 VARCHAR(64) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	mapping JSONB NOT NULL, 
	rows JSONB NOT NULL, 
	errors JSONB NOT NULL, 
	state VARCHAR(24) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	confirmed_at TIMESTAMP WITH TIME ZONE, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, fingerprint), 
	UNIQUE (tenant_id, id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_import_batches_tenant_id ON sg5_import_batches (tenant_id);

CREATE TABLE sg5_reports (
	created_by UUID NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	format VARCHAR(8) NOT NULL, 
	filename VARCHAR(160) NOT NULL, 
	content BYTEA NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	summary JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_reports_tenant_id ON sg5_reports (tenant_id);

CREATE TABLE sg5_subscriptions (
	name VARCHAR(100) NOT NULL, 
	topics JSONB NOT NULL, 
	created_by UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_subscriptions_tenant_id ON sg5_subscriptions (tenant_id);

CREATE TABLE sg5_records (
	kind VARCHAR(32) NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	source_ref VARCHAR(200) NOT NULL, 
	import_batch_id UUID, 
	created_by UUID NOT NULL, 
	payload JSONB NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, kind, code), 
	UNIQUE (tenant_id, id), 
	CHECK (kind in ('site','order','shipment','event','prediction','simulation')), 
	FOREIGN KEY(tenant_id, import_batch_id) REFERENCES sg5_import_batches (tenant_id, id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_records_kind ON sg5_records (kind);

CREATE INDEX ix_sg5_records_tenant_id ON sg5_records (tenant_id);

CREATE TABLE sg5_links (
	source_id UUID NOT NULL, 
	target_id UUID NOT NULL, 
	relation VARCHAR(32) NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_id, source_id, target_id, relation), 
	FOREIGN KEY(tenant_id, source_id) REFERENCES sg5_records (tenant_id, id), 
	FOREIGN KEY(tenant_id, target_id) REFERENCES sg5_records (tenant_id, id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_links_source_id ON sg5_links (source_id);

CREATE INDEX ix_sg5_links_tenant_id ON sg5_links (tenant_id);

CREATE TABLE sg5_tasks (
	record_id UUID NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	created_by UUID NOT NULL, 
	assignee_id UUID, 
	due_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	measures TEXT NOT NULL, 
	actual_cost_cny VARCHAR(32) NOT NULL, 
	result TEXT NOT NULL, 
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id, record_id) REFERENCES sg5_records (tenant_id, id), 
	CHECK (state in ('open','in_progress','pending_verification','completed','cancelled')), 
	CHECK (version >= 1), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(assignee_id) REFERENCES users (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_sg5_tasks_state ON sg5_tasks (state);

CREATE INDEX ix_sg5_tasks_tenant_id ON sg5_tasks (tenant_id);
