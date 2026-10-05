CREATE TABLE dependents (
	id UUID NOT NULL,
	patient_id UUID NOT NULL,
	full_name VARCHAR(100) NOT NULL,
	date_of_birth DATE,
	relationship_name VARCHAR(50) NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(patient_id) REFERENCES patient_profiles (id)
)

;
CREATE INDEX ix_dependents_patient_id ON dependents (patient_id);

CREATE TABLE waitlist_entries (
	id UUID NOT NULL,
	schedule_id UUID NOT NULL,
	patient_id UUID NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_waitlist_patient UNIQUE (schedule_id, patient_id),
	FOREIGN KEY(schedule_id) REFERENCES schedules (id),
	FOREIGN KEY(patient_id) REFERENCES patient_profiles (id)
)

;
CREATE INDEX ix_waitlist_entries_schedule_id ON waitlist_entries (schedule_id);
CREATE INDEX ix_waitlist_entries_patient_id ON waitlist_entries (patient_id);

CREATE TABLE notifications (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	channel VARCHAR(10) NOT NULL,
	subject VARCHAR(200) NOT NULL,
	message TEXT NOT NULL,
	deduplication_key VARCHAR(200),
	read_at TIMESTAMP WITH TIME ZONE,
	scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
	sent_at TIMESTAMP WITH TIME ZONE,
	attempts INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_notification_deduplication UNIQUE (deduplication_key),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
CREATE INDEX ix_notifications_scheduled_at ON notifications (scheduled_at);

CREATE TABLE account_actions (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	purpose VARCHAR(20) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	consumed_at TIMESTAMP WITH TIME ZONE,
	attempts INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	UNIQUE (token_hash)
)

;
CREATE INDEX ix_account_actions_user_id ON account_actions (user_id);

CREATE TABLE privacy_requests (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	kind VARCHAR(20) NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	resolved_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
CREATE INDEX ix_privacy_requests_user_id ON privacy_requests (user_id);

CREATE TABLE payments (
	id UUID NOT NULL,
	appointment_id UUID NOT NULL,
	amount NUMERIC(10, 2) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	status VARCHAR(20) NOT NULL,
	provider_reference VARCHAR(200),
	refund_reference VARCHAR(200),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	paid_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (appointment_id),
	FOREIGN KEY(appointment_id) REFERENCES appointments (id),
	UNIQUE (provider_reference)
)

;


CREATE TABLE availability_exceptions (
	id UUID NOT NULL,
	doctor_id UUID NOT NULL,
	exception_date DATE NOT NULL,
	reason VARCHAR(200) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_doctor_exception_date UNIQUE (doctor_id, exception_date),
	FOREIGN KEY(doctor_id) REFERENCES doctor_profiles (id)
)

;
CREATE INDEX ix_availability_exceptions_doctor_id ON availability_exceptions (doctor_id);
