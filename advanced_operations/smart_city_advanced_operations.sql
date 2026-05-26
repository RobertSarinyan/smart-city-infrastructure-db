SET search_path TO smart_city, public;


-- Section 1: Performance-Oriented Indexes
-- Purpose: Indexes speed up searches and joins on frequently used columns.
-- These indexes support the reporting queries and operational lookups.

CREATE INDEX IF NOT EXISTS idx_assets_zone
ON assets(zone_id);

CREATE INDEX IF NOT EXISTS idx_assets_type
ON assets(asset_type_id);

CREATE INDEX IF NOT EXISTS idx_sensors_asset
ON sensors(asset_id);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_time
ON sensor_readings(sensor_id, reading_time);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_quality
ON sensor_readings(quality_flag);

CREATE INDEX IF NOT EXISTS idx_incidents_asset
ON incidents(asset_id);

CREATE INDEX IF NOT EXISTS idx_incidents_status
ON incidents(status);

CREATE INDEX IF NOT EXISTS idx_incidents_severity
ON incidents(severity);

CREATE INDEX IF NOT EXISTS idx_work_orders_asset
ON maintenance_work_orders(asset_id);

CREATE INDEX IF NOT EXISTS idx_work_orders_status
ON maintenance_work_orders(status);

CREATE INDEX IF NOT EXISTS idx_assignments_user
ON work_order_assignments(user_id);

CREATE INDEX IF NOT EXISTS idx_dispatch_records_incident
ON dispatch_records(incident_id);

CREATE INDEX IF NOT EXISTS idx_dispatch_records_unit
ON dispatch_records(emergency_unit_id);

CREATE INDEX IF NOT EXISTS idx_transit_impacts_incident
ON incident_transit_impacts(incident_id);

CREATE INDEX IF NOT EXISTS idx_transit_impacts_route
ON incident_transit_impacts(route_id);


-- Section 2: Asset Status Audit Log
-- Purpose:
-- This table stores the history of asset status changes.
-- It supports audit trail / logging, which is one of the common trigger use cases

CREATE TABLE IF NOT EXISTS asset_status_log (
    log_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    old_status VARCHAR(30),
    new_status VARCHAR(30),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT NOT NULL DEFAULT CURRENT_USER,

    CONSTRAINT fk_asset_status_log_asset
        FOREIGN KEY (asset_id)
        REFERENCES assets(asset_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- Section 3: Trigger Function for Asset Status Logging
-- Purpose:
-- Automatically records a log row whenever asset.status changes.
-- This follows the trigger idea:
-- event = asset status update,
-- condition = old status is different from new status,
-- action = insert a record into the log table.

CREATE OR REPLACE FUNCTION log_asset_status_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO asset_status_log (
            asset_id,
            old_status,
            new_status
        )
        VALUES (
            NEW.asset_id,
            OLD.status,
            NEW.status
        );
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_log_asset_status_change ON assets;

CREATE TRIGGER trg_log_asset_status_change
AFTER UPDATE OF status ON assets
FOR EACH ROW
EXECUTE FUNCTION log_asset_status_change();


-- Section 4: Function for Refreshing Asset Status
-- Purpose:
-- Keeps asset status consistent with active incidents and work orders.
--
-- Business rule:
-- 1. If the asset has an active work order, mark it under_maintenance.
-- 2. Else if the asset has an unresolved incident, mark it under_incident.
-- 3. Otherwise, mark it active.
--
-- Inactive and retired assets are not automatically changed.

CREATE OR REPLACE FUNCTION refresh_asset_status(p_asset_id INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_status VARCHAR(30);
BEGIN
    SELECT status
    INTO v_current_status
    FROM assets
    WHERE asset_id = p_asset_id;

    IF v_current_status IS NULL THEN
        RAISE NOTICE 'Asset with id % does not exist.', p_asset_id;
        RETURN;
    END IF;

    IF v_current_status = 'inactive' OR v_current_status = 'retired' THEN
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM maintenance_work_orders
        WHERE asset_id = p_asset_id
          AND (
              status = 'open'
              OR status = 'assigned'
              OR status = 'in_progress'
          )
    ) THEN
        UPDATE assets
        SET status = 'under_maintenance'
        WHERE asset_id = p_asset_id;

    ELSIF EXISTS (
        SELECT 1
        FROM incidents
        WHERE asset_id = p_asset_id
          AND (
              status = 'detected'
              OR status = 'in_progress'
          )
    ) THEN
        UPDATE assets
        SET status = 'under_incident'
        WHERE asset_id = p_asset_id;

    ELSE
        UPDATE assets
        SET status = 'active'
        WHERE asset_id = p_asset_id;
    END IF;
END;
$$;


-- Section 5: Trigger After Incident Changes
-- Purpose:
-- Whenever an incident is inserted, updated, or deleted,
-- the affected asset status is refreshed automatically.

CREATE OR REPLACE FUNCTION refresh_asset_status_after_incident_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM refresh_asset_status(OLD.asset_id);
        RETURN OLD;
    ELSE
        PERFORM refresh_asset_status(NEW.asset_id);
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_refresh_asset_after_incident_change ON incidents;

CREATE TRIGGER trg_refresh_asset_after_incident_change
AFTER INSERT OR UPDATE OR DELETE ON incidents
FOR EACH ROW
EXECUTE FUNCTION refresh_asset_status_after_incident_change();


-- Section 6: Trigger After Work Order Changes
-- Purpose:
-- Whenever a work order is inserted, updated, or deleted,
-- the affected asset status is refreshed automatically.

CREATE OR REPLACE FUNCTION refresh_asset_status_after_work_order_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM refresh_asset_status(OLD.asset_id);
        RETURN OLD;
    ELSE
        PERFORM refresh_asset_status(NEW.asset_id);
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_refresh_asset_after_work_order_change ON maintenance_work_orders;

CREATE TRIGGER trg_refresh_asset_after_work_order_change
AFTER INSERT OR UPDATE OR DELETE ON maintenance_work_orders
FOR EACH ROW
EXECUTE FUNCTION refresh_asset_status_after_work_order_change();


-- Section 7: Function for Classifying Sensor Readings
-- Purpose:
-- Classifies a sensor value using the latest threshold rule.
--
-- Result:
-- critical -> reading is at or above the critical level
-- warning  -> reading is at or above the warning level
-- normal   -> reading is inside normal range
-- invalid  -> no matching interpretation is possible

CREATE OR REPLACE FUNCTION classify_sensor_reading(
    p_sensor_id INTEGER,
    p_reading_value NUMERIC
)
RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
DECLARE
    v_min_value NUMERIC;
    v_max_value NUMERIC;
    v_warning_level NUMERIC;
    v_critical_level NUMERIC;
BEGIN
    SELECT
        min_value,
        max_value,
        warning_level,
        critical_level
    INTO
        v_min_value,
        v_max_value,
        v_warning_level,
        v_critical_level
    FROM threshold_rules
    WHERE sensor_id = p_sensor_id
    ORDER BY effective_from DESC
    LIMIT 1;

    IF v_min_value IS NULL THEN
        RETURN 'invalid';
    END IF;

    IF p_reading_value >= v_critical_level THEN
        RETURN 'critical';
    ELSIF p_reading_value >= v_warning_level THEN
        RETURN 'warning';
    ELSIF p_reading_value BETWEEN v_min_value AND v_max_value THEN
        RETURN 'normal';
    ELSE
        RETURN 'invalid';
    END IF;
END;
$$;


-- Section 8: Trigger Function for Sensor Reading Validation
-- Purpose:
-- Before inserting a sensor reading, automatically classify it using
-- the threshold rule of that sensor.
-- This is an input validation / business rule trigger.

CREATE OR REPLACE FUNCTION set_sensor_reading_quality()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.quality_flag := classify_sensor_reading(
        NEW.sensor_id,
        NEW.reading_value
    );

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_set_sensor_reading_quality ON sensor_readings;

CREATE TRIGGER trg_set_sensor_reading_quality
BEFORE INSERT ON sensor_readings
FOR EACH ROW
EXECUTE FUNCTION set_sensor_reading_quality();


-- Section 9: Optional Function for Counting Active Incidents
-- Purpose:
-- Simple helper function that returns the number of active incidents for a given asset.

CREATE OR REPLACE FUNCTION count_active_incidents_for_asset(
    p_asset_id INTEGER
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_total INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_total
    FROM incidents
    WHERE asset_id = p_asset_id
      AND (
          status = 'detected'
          OR status = 'in_progress'
      );

    RETURN v_total;
END;
$$;


-- Some examples that can be ran manually to show index access paths.
-- They are commented out so the full script can be executed safely.


-- EXPLAIN
-- SELECT *
-- FROM incidents
-- WHERE status = 'detected';

-- EXPLAIN
-- SELECT *
-- FROM incidents
-- WHERE severity = 'critical';

-- EXPLAIN
-- SELECT *
-- FROM sensor_readings
-- WHERE sensor_id = 1
-- ORDER BY reading_time DESC;

-- EXPLAIN
-- SELECT *
-- FROM maintenance_work_orders
-- WHERE asset_id = 1
--   AND status = 'open';



-- These examples show how the functions can be used. Again commented out.


-- SELECT classify_sensor_reading(1, 150.00);

-- SELECT count_active_incidents_for_asset(1);

-- UPDATE assets
-- SET status = 'under_maintenance'
-- WHERE asset_id = 1;