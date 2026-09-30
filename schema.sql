CREATE TABLE IF NOT EXISTS contacts (
    hubspot_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lifecycle_stage TEXT;

CREATE TABLE IF NOT EXISTS lead_alerts (
    hubspot_id TEXT PRIMARY KEY REFERENCES contacts(hubspot_id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'attempted', 'sent')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMPTZ
);
