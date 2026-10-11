-- Central index of company capacity profiles. Idempotent: applied on every start.
-- One row per company that opted in. Aggregates only: the company app never sends clients, prices, invoices, plates or drivers.
CREATE TABLE IF NOT EXISTS companies (
    company_uid           text PRIMARY KEY,
    name                  text    NOT NULL,
    name_latin            text    NOT NULL DEFAULT '',
    home_region           text    NOT NULL DEFAULT '',
    countries             text[]  NOT NULL DEFAULT '{}',
    trailer_types         text[]  NOT NULL DEFAULT '{}',
    cargo_types           text[]  NOT NULL DEFAULT '{}',
    languages             text[]  NOT NULL DEFAULT '{}',
    adr                   boolean NOT NULL DEFAULT false,
    max_load_kg           integer NOT NULL DEFAULT 0,
    fleet_trucks          integer NOT NULL DEFAULT 0,
    fleet_max_capacity_kg integer NOT NULL DEFAULT 0,
    lanes                 jsonb   NOT NULL DEFAULT '[]',
    public_notes          text    NOT NULL DEFAULT '',
    contact_email         text,   -- only present when the company chose to share a contact
    contact_phone         text,
    profile               jsonb   NOT NULL,        -- the full document as received (what search returns)
    schema_version        integer NOT NULL,
    published_at          timestamptz NOT NULL,    -- the company's own timestamp: older updates never overwrite newer ones
    received_at           timestamptz NOT NULL DEFAULT now(),
    -- free-text search over names, region and notes ('simple' = no language-specific stemming, works for Cyrillic too)
    search tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', name || ' ' || name_latin || ' ' || home_region || ' ' || public_notes)
    ) STORED
);

CREATE INDEX IF NOT EXISTS companies_countries_gin ON companies USING gin (countries);
CREATE INDEX IF NOT EXISTS companies_trailers_gin  ON companies USING gin (trailer_types);
CREATE INDEX IF NOT EXISTS companies_cargo_gin     ON companies USING gin (cargo_types);
CREATE INDEX IF NOT EXISTS companies_languages_gin ON companies USING gin (languages);
CREATE INDEX IF NOT EXISTS companies_lanes_gin     ON companies USING gin (lanes jsonb_path_ops);
CREATE INDEX IF NOT EXISTS companies_search_gin    ON companies USING gin (search);
CREATE INDEX IF NOT EXISTS companies_max_load      ON companies (max_load_kg);
