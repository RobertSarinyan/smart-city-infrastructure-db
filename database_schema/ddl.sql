DROP SCHEMA IF EXISTS smart_city CASCADE;
CREATE SCHEMA smart_city;
SET search_path TO smart_city, public;

-- Reference tables

CREATE TABLE roles (
    role_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name    VARCHAR(50) NOT NULL UNIQUE,
    description  TEXT
);

CREATE TABLE zones (
    zone_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_name       VARCHAR(100) NOT NULL,
    district_name   VARCHAR(100) NOT NULL,
    description     TEXT,
    CONSTRAINT uq_zones UNIQUE (zone_name, district_name)
);

CREATE TABLE asset_types (
    asset_type_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type_name      VARCHAR(100) NOT NULL UNIQUE,
    description    TEXT
);

-- Core user / staff tables

CREATE TABLE users (
    user_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_id         INTEGER NOT NULL,
    first_name      VARCHAR(60) NOT NULL,
    last_name       VARCHAR(60) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone_number    VARCHAR(30),
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_users_role
        FOREIGN KEY (role_id)
        REFERENCES roles(role_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_users_status
        CHECK (status IN ('active', 'inactive', 'suspended'))
);

-- Infrastructure tables

CREATE TABLE assets (
    asset_id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_id             INTEGER NOT NULL,
    asset_type_id       INTEGER NOT NULL,
    asset_name          VARCHAR(150) NOT NULL,
    latitude            NUMERIC(9,6) NOT NULL,
    longitude           NUMERIC(9,6) NOT NULL,
    installation_date   DATE NOT NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'active',

    CONSTRAINT fk_assets_zone
        FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_assets_asset_type
        FOREIGN KEY (asset_type_id)
        REFERENCES asset_types(asset_type_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_assets_status
        CHECK (status IN ('active', 'inactive', 'under_maintenance', 'under_incident', 'retired')),

    CONSTRAINT chk_assets_latitude
        CHECK (latitude BETWEEN -90 AND 90),

    CONSTRAINT chk_assets_longitude
        CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE sensors (
    sensor_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id           INTEGER NOT NULL,
    sensor_type        VARCHAR(60) NOT NULL,
    measurement_unit   VARCHAR(40) NOT NULL,
    installed_at       TIMESTAMP NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'active',

    CONSTRAINT fk_sensors_asset
        FOREIGN KEY (asset_id)
        REFERENCES assets(asset_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_sensors_status
        CHECK (status IN ('active', 'inactive', 'faulty', 'maintenance')),

    -- need this so incidents can safely reference (sensor_id, asset_id)
    CONSTRAINT uq_sensors_sensor_asset
        UNIQUE (sensor_id, asset_id)
);

CREATE TABLE threshold_rules (
    threshold_rule_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensor_id           INTEGER NOT NULL,
    effective_from      TIMESTAMP NOT NULL,
    min_value           NUMERIC(14,4) NOT NULL,
    max_value           NUMERIC(14,4) NOT NULL,
    warning_level       NUMERIC(14,4) NOT NULL,
    critical_level      NUMERIC(14,4) NOT NULL,

    CONSTRAINT fk_threshold_rules_sensor
        FOREIGN KEY (sensor_id)
        REFERENCES sensors(sensor_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT uq_threshold_rules_sensor_effective
        UNIQUE (sensor_id, effective_from),

    CONSTRAINT chk_threshold_rules_range
        CHECK (min_value <= max_value),

    CONSTRAINT chk_threshold_rules_levels
        CHECK (warning_level <= critical_level)
);

CREATE TABLE sensor_readings (
    reading_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensor_id        INTEGER NOT NULL,
    reading_value    NUMERIC(14,4) NOT NULL,
    reading_time     TIMESTAMP NOT NULL,
    quality_flag     VARCHAR(20) NOT NULL DEFAULT 'normal',

    CONSTRAINT fk_sensor_readings_sensor
        FOREIGN KEY (sensor_id)
        REFERENCES sensors(sensor_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT uq_sensor_readings_sensor_time
        UNIQUE (sensor_id, reading_time),

    CONSTRAINT chk_sensor_readings_quality
        CHECK (quality_flag IN ('normal', 'warning', 'critical', 'invalid'))
);

-- Incident and maintenance tables

CREATE TABLE incidents (
    incident_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id         INTEGER NOT NULL,
    sensor_id        INTEGER NULL,
    incident_type    VARCHAR(80) NOT NULL,
    severity         VARCHAR(20) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'detected',
    description      TEXT NOT NULL,
    detected_at      TIMESTAMP NOT NULL,
    resolved_at      TIMESTAMP NULL,

    CONSTRAINT fk_incidents_asset
        FOREIGN KEY (asset_id)
        REFERENCES assets(asset_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    -- if sensor_id is provided, it must belong to the same asset.
    CONSTRAINT fk_incidents_sensor_asset
        FOREIGN KEY (sensor_id, asset_id)
        REFERENCES sensors(sensor_id, asset_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT uq_incidents_incident_asset
        UNIQUE (incident_id, asset_id),

    CONSTRAINT chk_incidents_severity
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),

    CONSTRAINT chk_incidents_status
        CHECK (status IN ('detected', 'in_progress', 'resolved', 'closed')),

    CONSTRAINT chk_incidents_time
        CHECK (resolved_at IS NULL OR resolved_at >= detected_at)
);

CREATE TABLE maintenance_work_orders (
    work_order_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id           INTEGER NOT NULL,
    asset_id              INTEGER NOT NULL,
    priority              VARCHAR(20) NOT NULL DEFAULT 'medium',
    status                VARCHAR(20) NOT NULL DEFAULT 'open',
    problem_description   TEXT NOT NULL,
    resolution_summary    TEXT,
    opened_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at             TIMESTAMP NULL,

    CONSTRAINT fk_work_orders_asset
        FOREIGN KEY (asset_id)
        REFERENCES assets(asset_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    -- ensures the work order references the same asset as the incident.
    CONSTRAINT fk_work_orders_incident_asset
        FOREIGN KEY (incident_id, asset_id)
        REFERENCES incidents(incident_id, asset_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_work_orders_priority
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),

    CONSTRAINT chk_work_orders_status
        CHECK (status IN ('open', 'assigned', 'in_progress', 'completed', 'closed', 'cancelled')),

    CONSTRAINT chk_work_orders_time
        CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE work_order_assignments (
    assignment_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_order_id        INTEGER NOT NULL,
    user_id              INTEGER NOT NULL,
    assigned_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    released_at          TIMESTAMP NULL,
    assignment_role      VARCHAR(60) NOT NULL,
    assignment_status    VARCHAR(20) NOT NULL DEFAULT 'assigned',

    CONSTRAINT fk_work_order_assignments_work_order
        FOREIGN KEY (work_order_id)
        REFERENCES maintenance_work_orders(work_order_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_work_order_assignments_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_work_order_assignments_status
        CHECK (assignment_status IN ('assigned', 'active', 'released', 'completed', 'cancelled')),

    CONSTRAINT chk_work_order_assignments_time
        CHECK (released_at IS NULL OR released_at >= assigned_at),

	CONSTRAINT uq_work_order_user_assignment
		UNIQUE (work_order_id, user_id)
);

-- Emergency response tables

CREATE TABLE emergency_units (
    emergency_unit_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unit_name           VARCHAR(100) NOT NULL UNIQUE,
    unit_type           VARCHAR(50) NOT NULL,
    base_location       VARCHAR(150) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'available',

    CONSTRAINT chk_emergency_units_status
        CHECK (status IN ('available', 'dispatched', 'busy', 'maintenance', 'out_of_service'))
);

CREATE TABLE dispatch_records (
    dispatch_id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id           INTEGER NOT NULL,
    emergency_unit_id     INTEGER NOT NULL,
    dispatcher_user_id    INTEGER NOT NULL,
    dispatch_time         TIMESTAMP NOT NULL,
    arrival_time          TIMESTAMP NULL,
    completion_time       TIMESTAMP NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'dispatched',

    CONSTRAINT fk_dispatch_records_incident
        FOREIGN KEY (incident_id)
        REFERENCES incidents(incident_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_dispatch_records_emergency_unit
        FOREIGN KEY (emergency_unit_id)
        REFERENCES emergency_units(emergency_unit_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_dispatch_records_dispatcher
        FOREIGN KEY (dispatcher_user_id)
        REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_dispatch_records_status
        CHECK (status IN ('dispatched', 'en_route', 'arrived', 'completed', 'cancelled')),

    CONSTRAINT chk_dispatch_arrival_time
        CHECK (arrival_time IS NULL OR arrival_time >= dispatch_time),

    CONSTRAINT chk_dispatch_completion_time
        CHECK (
            completion_time IS NULL
            OR completion_time >= COALESCE(arrival_time, dispatch_time)
        )
);

-- Transit tables

CREATE TABLE transit_routes (
    route_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_name     VARCHAR(100) NOT NULL,
    route_code     VARCHAR(30) NOT NULL UNIQUE,
    status         VARCHAR(20) NOT NULL DEFAULT 'active',

    CONSTRAINT chk_transit_routes_status
        CHECK (status IN ('active', 'delayed', 'suspended', 'inactive'))
);

CREATE TABLE transit_vehicles (
    vehicle_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_number     VARCHAR(30) NOT NULL UNIQUE,
    vehicle_type       VARCHAR(50) NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'active',

    CONSTRAINT chk_transit_vehicles_status
        CHECK (status IN ('active', 'delayed', 'maintenance', 'out_of_service'))
);

CREATE TABLE incident_transit_impacts (
    impact_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id      INTEGER NOT NULL,
    route_id         INTEGER NOT NULL,
    vehicle_id       INTEGER NOT NULL,
    impact_type      VARCHAR(50) NOT NULL,
    delay_minutes    INTEGER NOT NULL DEFAULT 0,
    recorded_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status           VARCHAR(20) NOT NULL DEFAULT 'active',

    CONSTRAINT fk_incident_transit_impacts_incident
        FOREIGN KEY (incident_id)
        REFERENCES incidents(incident_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_incident_transit_impacts_route
        FOREIGN KEY (route_id)
        REFERENCES transit_routes(route_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_incident_transit_impacts_vehicle
        FOREIGN KEY (vehicle_id)
        REFERENCES transit_vehicles(vehicle_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_incident_transit_impacts_delay
        CHECK (delay_minutes >= 0),

    CONSTRAINT chk_incident_transit_impacts_status
        CHECK (status IN ('active', 'resolved', 'logged'))
);