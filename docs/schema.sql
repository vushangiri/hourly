
CREATE TABLE login_buckets (
	key VARCHAR(64) NOT NULL, 
	count INTEGER NOT NULL, 
	expires TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;
CREATE INDEX ix_login_buckets_expires ON login_buckets (expires);

CREATE TABLE users (
	id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	password_hash TEXT NOT NULL, 
	timezone VARCHAR(80) NOT NULL, 
	session_version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	UNIQUE (phone)
)

;

CREATE TABLE idempotency_keys (
	user_id UUID NOT NULL, 
	key UUID NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	response JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id, key), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE TABLE reset_tokens (
	digest VARCHAR(64) NOT NULL, 
	user_id UUID NOT NULL, 
	expires TIMESTAMP WITH TIME ZONE NOT NULL, 
	used BOOLEAN NOT NULL, 
	PRIMARY KEY (digest), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
CREATE INDEX ix_reset_tokens_user_id ON reset_tokens (user_id);

CREATE TABLE workplaces (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	contact VARCHAR(200) NOT NULL, 
	archived BOOLEAN NOT NULL, 
	revision INTEGER NOT NULL, 
	cursor DATE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
CREATE INDEX ix_workplaces_user_id ON workplaces (user_id);

CREATE TABLE payment_confirmations (
	id UUID NOT NULL, 
	workplace_id UUID NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	paid_date DATE NOT NULL, 
	actual_amount NUMERIC(14, 2), 
	confirmed_estimate NUMERIC(14, 2) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workplace_id, period_start, period_end), 
	CHECK (period_end >= period_start), 
	FOREIGN KEY(workplace_id) REFERENCES workplaces (id)
)

;
CREATE INDEX ix_payment_confirmations_workplace_id ON payment_confirmations (workplace_id);

CREATE TABLE schedule_revisions (
	id UUID NOT NULL, 
	workplace_id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	effective_date DATE NOT NULL, 
	config JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workplace_id, revision), 
	FOREIGN KEY(workplace_id) REFERENCES workplaces (id)
)

;
CREATE INDEX ix_schedule_revisions_workplace_id ON schedule_revisions (workplace_id);

CREATE TABLE shifts (
	id UUID NOT NULL, 
	workplace_id UUID NOT NULL, 
	local_date DATE NOT NULL, 
	slot VARCHAR(40) NOT NULL, 
	start_at TIMESTAMP WITH TIME ZONE, 
	end_at TIMESTAMP WITH TIME ZONE, 
	timezone VARCHAR(80) NOT NULL, 
	break_minutes INTEGER NOT NULL, 
	net_seconds INTEGER NOT NULL, 
	rate NUMERIC(12, 2) NOT NULL, 
	earnings NUMERIC(14, 2) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	origin VARCHAR(16) NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workplace_id, local_date, slot), 
	CHECK (status IN ('manual','auto','off','planned')), 
	CHECK (origin IN ('manual','auto')), 
	CHECK (net_seconds >= 0 AND break_minutes >= 0 AND rate >= 0 AND earnings >= 0), 
	CHECK (status = 'off' OR (end_at > start_at AND start_at IS NOT NULL AND end_at IS NOT NULL)), 
	FOREIGN KEY(workplace_id) REFERENCES workplaces (id)
)

;
CREATE INDEX ix_shift_workplace_date ON shifts (workplace_id, local_date);

CREATE TABLE shift_revisions (
	id SERIAL NOT NULL, 
	shift_id UUID NOT NULL, 
	actor_id UUID, 
	action VARCHAR(30) NOT NULL, 
	snapshot JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(shift_id) REFERENCES shifts (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;
CREATE INDEX ix_shift_revisions_shift_id ON shift_revisions (shift_id);
