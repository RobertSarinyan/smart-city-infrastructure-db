from __future__ import annotations

import argparse
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


SEED = 205326

INSTALLATION_START_DATE = date(2020, 1, 1)
INSTALLATION_END_DATE = date(2025, 9, 30)

READING_WINDOW_START = datetime(2026, 3, 1, 0, 0, 0)
READING_WINDOW_END = datetime(2026, 3, 14, 23, 59, 59)
READING_INTERVAL_HOURS = 3
READING_TIME_JITTER_MINUTES = 15

ROLE_SPECS = [
    ("Administrator", "Manages system access, configuration, and administrative control."),
    ("System Operator", "Monitors assets, sensor activity, and incident workflows."),
    ("Maintenance Supervisor", "Oversees maintenance planning and technician coordination."),
    ("Maintenance Technician", "Performs field repairs and maintenance operations."),
    ("Dispatcher", "Coordinates emergency response unit dispatch operations."),
    ("Field Inspector", "Conducts inspections and manually reports infrastructure issues."),
]

ROLE_DISTRIBUTION = {
    "Administrator": 4,
    "System Operator": 14,
    "Maintenance Supervisor": 10,
    "Maintenance Technician": 58,
    "Dispatcher": 14,
    "Field Inspector": 20,
}

ZONE_SPECS = [
    {"zone_name": "Kentron North", "district_name": "Kentron", "description": "Northern operational area of Kentron.", "center_lat": 40.1845, "center_lon": 44.5152, "profile": "central", "transit_priority": 0.16, "asset_count": 110},
    {"zone_name": "Kentron South", "district_name": "Kentron", "description": "Southern operational area of Kentron.", "center_lat": 40.1760, "center_lon": 44.5105, "profile": "central", "transit_priority": 0.18, "asset_count": 110},
    {"zone_name": "Arabkir East", "district_name": "Arabkir", "description": "Eastern operational area of Arabkir.", "center_lat": 40.2040, "center_lon": 44.5160, "profile": "mixed", "transit_priority": 0.08, "asset_count": 90},
    {"zone_name": "Arabkir West", "district_name": "Arabkir", "description": "Western operational area of Arabkir.", "center_lat": 40.2075, "center_lon": 44.5010, "profile": "mixed", "transit_priority": 0.06, "asset_count": 85},
    {"zone_name": "Ajapnyak Central", "district_name": "Ajapnyak", "description": "Central operational area of Ajapnyak.", "center_lat": 40.1980, "center_lon": 44.4690, "profile": "residential", "transit_priority": 0.09, "asset_count": 110},
    {"zone_name": "Davtashen Riverside", "district_name": "Davtashen", "description": "Riverside operational area of Davtashen.", "center_lat": 40.2165, "center_lon": 44.4930, "profile": "residential", "transit_priority": 0.07, "asset_count": 85},
    {"zone_name": "Avan North", "district_name": "Avan", "description": "Northern operational area of Avan.", "center_lat": 40.2215, "center_lon": 44.5710, "profile": "residential", "transit_priority": 0.05, "asset_count": 75},
    {"zone_name": "Kanaker-Zeytun Central", "district_name": "Kanaker-Zeytun", "description": "Central operational area of Kanaker-Zeytun.", "center_lat": 40.2100, "center_lon": 44.5360, "profile": "mixed", "transit_priority": 0.07, "asset_count": 85},
    {"zone_name": "Nor Nork East", "district_name": "Nor Nork", "description": "Eastern operational area of Nor Nork.", "center_lat": 40.2020, "center_lon": 44.5615, "profile": "residential", "transit_priority": 0.06, "asset_count": 90},
    {"zone_name": "Erebuni South", "district_name": "Erebuni", "description": "Southern operational area of Erebuni.", "center_lat": 40.1525, "center_lon": 44.5325, "profile": "industrial", "transit_priority": 0.10, "asset_count": 115},
    {"zone_name": "Shengavit Central", "district_name": "Shengavit", "description": "Central operational area of Shengavit.", "center_lat": 40.1605, "center_lon": 44.4965, "profile": "transit", "transit_priority": 0.20, "asset_count": 130},
    {"zone_name": "Malatia-Sebastia West", "district_name": "Malatia-Sebastia", "description": "Western operational area of Malatia-Sebastia.", "center_lat": 40.1735, "center_lon": 44.4630, "profile": "logistics", "transit_priority": 0.14, "asset_count": 115},
]

ASSET_TYPE_SPECS = [
    ("Water Pump Station", "Pumping facility used for water distribution and pressure support."),
    ("Water Pipeline Segment", "Monitored segment of water distribution pipeline."),
    ("Electrical Transformer Unit", "Electrical transformer or distribution unit serving city infrastructure."),
    ("Street Lighting Unit", "Smart street lighting installation with operational monitoring."),
    ("Traffic Signal Controller", "Intersection traffic signal control system."),
    ("Roadside Traffic Sensor Hub", "Roadside monitoring unit collecting traffic-related measurements."),
    ("Waste Collection Unit", "Smart waste collection container or collection point."),
    ("Environmental Monitoring Station", "Station for measuring environmental conditions and air quality."),
]

ASSET_TYPE_CODES = {
    "Water Pump Station": "WPS",
    "Water Pipeline Segment": "WPL",
    "Electrical Transformer Unit": "ETU",
    "Street Lighting Unit": "SLU",
    "Traffic Signal Controller": "TSC",
    "Roadside Traffic Sensor Hub": "RTH",
    "Waste Collection Unit": "WCU",
    "Environmental Monitoring Station": "EMS",
}

PROFILE_ASSET_WEIGHTS = {
    "central": {
        "Water Pump Station": 0.04,
        "Water Pipeline Segment": 0.12,
        "Electrical Transformer Unit": 0.12,
        "Street Lighting Unit": 0.22,
        "Traffic Signal Controller": 0.18,
        "Roadside Traffic Sensor Hub": 0.18,
        "Waste Collection Unit": 0.10,
        "Environmental Monitoring Station": 0.04,
    },
    "transit": {
        "Water Pump Station": 0.03,
        "Water Pipeline Segment": 0.10,
        "Electrical Transformer Unit": 0.12,
        "Street Lighting Unit": 0.18,
        "Traffic Signal Controller": 0.22,
        "Roadside Traffic Sensor Hub": 0.23,
        "Waste Collection Unit": 0.07,
        "Environmental Monitoring Station": 0.05,
    },
    "industrial": {
        "Water Pump Station": 0.12,
        "Water Pipeline Segment": 0.18,
        "Electrical Transformer Unit": 0.22,
        "Street Lighting Unit": 0.13,
        "Traffic Signal Controller": 0.10,
        "Roadside Traffic Sensor Hub": 0.08,
        "Waste Collection Unit": 0.07,
        "Environmental Monitoring Station": 0.10,
    },
    "logistics": {
        "Water Pump Station": 0.06,
        "Water Pipeline Segment": 0.15,
        "Electrical Transformer Unit": 0.18,
        "Street Lighting Unit": 0.12,
        "Traffic Signal Controller": 0.15,
        "Roadside Traffic Sensor Hub": 0.16,
        "Waste Collection Unit": 0.10,
        "Environmental Monitoring Station": 0.08,
    },
    "residential": {
        "Water Pump Station": 0.07,
        "Water Pipeline Segment": 0.18,
        "Electrical Transformer Unit": 0.11,
        "Street Lighting Unit": 0.22,
        "Traffic Signal Controller": 0.12,
        "Roadside Traffic Sensor Hub": 0.08,
        "Waste Collection Unit": 0.16,
        "Environmental Monitoring Station": 0.06,
    },
    "mixed": {
        "Water Pump Station": 0.06,
        "Water Pipeline Segment": 0.15,
        "Electrical Transformer Unit": 0.14,
        "Street Lighting Unit": 0.17,
        "Traffic Signal Controller": 0.14,
        "Roadside Traffic Sensor Hub": 0.12,
        "Waste Collection Unit": 0.12,
        "Environmental Monitoring Station": 0.10,
    },
}

ASSET_SENSOR_MAP = {
    "Water Pump Station": ["pressure_sensor", "flow_sensor", "vibration_sensor", "water_level_sensor"],
    "Water Pipeline Segment": ["pressure_sensor", "flow_sensor", "pipeline_temperature_sensor"],
    "Electrical Transformer Unit": ["voltage_sensor", "current_sensor", "transformer_temperature_sensor", "load_sensor"],
    "Street Lighting Unit": ["voltage_sensor", "power_draw_sensor", "controller_temperature_sensor"],
    "Traffic Signal Controller": ["cycle_delay_sensor", "voltage_sensor", "controller_temperature_sensor"],
    "Roadside Traffic Sensor Hub": ["traffic_volume_sensor", "queue_length_sensor", "occupancy_rate_sensor", "device_temperature_sensor"],
    "Waste Collection Unit": ["fill_level_sensor", "internal_temperature_sensor", "gas_level_sensor"],
    "Environmental Monitoring Station": ["air_temperature_sensor", "humidity_sensor", "pm25_sensor", "co2_sensor"],
}

SENSOR_LIBRARY = {
    "pressure_sensor": {"measurement_unit": "bar", "min": 2.5, "max": 6.5, "warning": 6.8, "critical": 7.5},
    "flow_sensor": {"measurement_unit": "l/min", "min": 250.0, "max": 900.0, "warning": 980.0, "critical": 1100.0},
    "vibration_sensor": {"measurement_unit": "mm/s", "min": 0.5, "max": 4.0, "warning": 4.8, "critical": 6.2},
    "water_level_sensor": {"measurement_unit": "%", "min": 35.0, "max": 85.0, "warning": 90.0, "critical": 97.0},
    "pipeline_temperature_sensor": {"measurement_unit": "°C", "min": 5.0, "max": 30.0, "warning": 35.0, "critical": 42.0},
    "voltage_sensor": {"measurement_unit": "V", "min": 210.0, "max": 240.0, "warning": 245.0, "critical": 255.0},
    "current_sensor": {"measurement_unit": "A", "min": 60.0, "max": 180.0, "warning": 195.0, "critical": 215.0},
    "transformer_temperature_sensor": {"measurement_unit": "°C", "min": 40.0, "max": 80.0, "warning": 90.0, "critical": 102.0},
    "load_sensor": {"measurement_unit": "%", "min": 40.0, "max": 80.0, "warning": 90.0, "critical": 98.0},
    "power_draw_sensor": {"measurement_unit": "kW", "min": 0.4, "max": 3.0, "warning": 3.5, "critical": 4.2},
    "controller_temperature_sensor": {"measurement_unit": "°C", "min": 20.0, "max": 55.0, "warning": 62.0, "critical": 72.0},
    "cycle_delay_sensor": {"measurement_unit": "sec", "min": 5.0, "max": 55.0, "warning": 70.0, "critical": 95.0},
    "traffic_volume_sensor": {"measurement_unit": "veh/5min", "min": 80.0, "max": 650.0, "warning": 750.0, "critical": 900.0},
    "queue_length_sensor": {"measurement_unit": "vehicles", "min": 0.0, "max": 18.0, "warning": 24.0, "critical": 35.0},
    "occupancy_rate_sensor": {"measurement_unit": "%", "min": 10.0, "max": 55.0, "warning": 70.0, "critical": 85.0},
    "device_temperature_sensor": {"measurement_unit": "°C", "min": 15.0, "max": 45.0, "warning": 52.0, "critical": 65.0},
    "fill_level_sensor": {"measurement_unit": "%", "min": 10.0, "max": 75.0, "warning": 85.0, "critical": 95.0},
    "internal_temperature_sensor": {"measurement_unit": "°C", "min": 10.0, "max": 35.0, "warning": 42.0, "critical": 52.0},
    "gas_level_sensor": {"measurement_unit": "ppm", "min": 5.0, "max": 55.0, "warning": 70.0, "critical": 90.0},
    "air_temperature_sensor": {"measurement_unit": "°C", "min": -5.0, "max": 35.0, "warning": 39.0, "critical": 45.0},
    "humidity_sensor": {"measurement_unit": "%", "min": 20.0, "max": 70.0, "warning": 80.0, "critical": 92.0},
    "pm25_sensor": {"measurement_unit": "ug/m3", "min": 0.0, "max": 35.0, "warning": 55.0, "critical": 80.0},
    "co2_sensor": {"measurement_unit": "ppm", "min": 350.0, "max": 900.0, "warning": 1200.0, "critical": 1700.0},
}

FIRST_NAMES = [
    "Arman", "Narek", "Hayk", "Tigran", "Gor", "David", "Robert", "Samvel", "Karen", "Vardan",
    "Levon", "Ashot", "Erik", "Mher", "Suren", "Artur", "Anna", "Mariam", "Mane", "Lilit",
    "Ani", "Meri", "Sona", "Narine", "Karine", "Anahit", "Gayane", "Tamara", "Milena", "Eva",
]

LAST_NAMES = [
    "Sargsyan", "Hakobyan", "Petrosyan", "Karapetyan", "Harutyunyan", "Vardanyan", "Mkrtchyan",
    "Khachatryan", "Grigoryan", "Avetisyan", "Poghosyan", "Manukyan", "Baghdasaryan", "Melkonyan",
    "Yeghiazaryan", "Gevorgyan", "Martirosyan", "Sahakyan", "Davtyan", "Asatryan",
]

USER_STATUS_WEIGHTS = {"active": 0.87, "inactive": 0.10, "suspended": 0.03}
ASSET_STATUS_WEIGHTS = {"active": 0.95, "inactive": 0.03, "retired": 0.02}
SENSOR_STATUS_WEIGHTS = {"active": 0.91, "inactive": 0.03, "faulty": 0.04, "maintenance": 0.02}
ACTIVE_SENSOR_QUALITY_WEIGHTS = {"normal": 93.0, "warning": 5.0, "critical": 1.5, "invalid": 0.5}
FAULTY_SENSOR_QUALITY_WEIGHTS = {"normal": 60.0, "warning": 12.0, "critical": 8.0, "invalid": 20.0}

TARGET_INCIDENTS = 1100
TARGET_EMERGENCY_UNITS = 30
TARGET_TRANSIT_ROUTES = 24
TARGET_TRANSIT_VEHICLES = 180

WORK_ORDER_PROBABILITY = {"critical": 0.95, "high": 0.75, "medium": 0.45, "low": 0.15}

UNIT_TYPE_BY_ASSET_TYPE = {
    "Water Pump Station": "Water Response Unit",
    "Water Pipeline Segment": "Water Response Unit",
    "Electrical Transformer Unit": "Electrical Response Unit",
    "Street Lighting Unit": "Technical Response Unit",
    "Traffic Signal Controller": "Traffic Response Unit",
    "Roadside Traffic Sensor Hub": "Traffic Response Unit",
    "Waste Collection Unit": "Technical Response Unit",
    "Environmental Monitoring Station": "Environmental Response Unit",
}

MANUAL_INCIDENT_SHARE = 0.28

TABLE_ORDER = [
    "roles",
    "zones",
    "asset_types",
    "users",
    "assets",
    "sensors",
    "threshold_rules",
    "sensor_readings",
    "incidents",
    "maintenance_work_orders",
    "work_order_assignments",
    "emergency_units",
    "dispatch_records",
    "transit_routes",
    "transit_vehicles",
    "incident_transit_impacts",
]

TRUNCATE_ORDER = [
    "incident_transit_impacts",
    "dispatch_records",
    "work_order_assignments",
    "maintenance_work_orders",
    "sensor_readings",
    "threshold_rules",
    "transit_vehicles",
    "transit_routes",
    "emergency_units",
    "incidents",
    "sensors",
    "assets",
    "users",
    "asset_types",
    "zones",
    "roles",
]


def weighted_choice(rng: random.Random, weighted_items: dict[str, float]) -> str:
    items = list(weighted_items.keys())
    weights = list(weighted_items.values())
    return rng.choices(items, weights=weights, k=1)[0]


def weighted_sample_without_replacement(
    rng: random.Random,
    items: list[str],
    weights: list[float],
    sample_size: int,
) -> list[str]:
    available_items = items.copy()
    available_weights = weights.copy()
    chosen: list[str] = []
    for _ in range(min(sample_size, len(available_items))):
        item = rng.choices(available_items, weights=available_weights, k=1)[0]
        idx = available_items.index(item)
        chosen.append(item)
        del available_items[idx]
        del available_weights[idx]
    return chosen


def random_date(rng: random.Random, start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, delta_days))


def random_datetime(rng: random.Random, start: datetime, end: datetime) -> datetime:
    total_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, total_seconds))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def zone_code(zone_name: str) -> str:
    tokens = zone_name.replace("-", " ").split()
    return "".join(token[0].upper() for token in tokens[:3])


def choose_status_by_weights(rng: random.Random, weights: dict[str, float]) -> str:
    return weighted_choice(rng, weights)


def make_insert_sql(cur: Any, schema: str, table_name: str, columns: list[str]) -> str:
    stmt = sql.SQL("INSERT INTO {}.{} ({}) VALUES %s").format(
        sql.Identifier(schema),
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(col) for col in columns),
    )
    return stmt.as_string(cur.connection)


def bulk_insert(cur: Any, schema: str, table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    values = [tuple(row[col] for col in columns) for row in rows]
    insert_sql = make_insert_sql(cur, schema, table_name, columns)
    execute_values(cur, insert_sql, values, page_size=1000)


def fetch_id_map(cur: Any, schema: str, table_name: str, key_col: str, id_col: str) -> dict[Any, int]:
    query = sql.SQL("SELECT {}, {} FROM {}.{}").format(
        sql.Identifier(key_col),
        sql.Identifier(id_col),
        sql.Identifier(schema),
        sql.Identifier(table_name),
    )
    cur.execute(query)
    return {row[0]: row[1] for row in cur.fetchall()}


def fetch_zone_map(cur: Any, schema: str) -> dict[tuple[str, str], int]:
    query = sql.SQL("SELECT zone_name, district_name, zone_id FROM {}.zones").format(sql.Identifier(schema))
    cur.execute(query)
    return {(row[0], row[1]): row[2] for row in cur.fetchall()}


def fetch_assets(cur: Any, schema: str) -> list[tuple[int, str, str]]:
    query = sql.SQL("SELECT asset_id, asset_name, status FROM {}.assets ORDER BY asset_id").format(sql.Identifier(schema))
    cur.execute(query)
    return cur.fetchall()


def fetch_sensors(cur: Any, schema: str) -> list[tuple[int, int, str, datetime, str]]:
    query = sql.SQL(
        "SELECT sensor_id, asset_id, sensor_type, installed_at, status "
        "FROM {}.sensors ORDER BY sensor_id"
    ).format(sql.Identifier(schema))
    cur.execute(query)
    return cur.fetchall()


def fetch_active_users_by_role(cur: Any, schema: str) -> dict[str, list[int]]:
    query = sql.SQL(
        "SELECT r.role_name, u.user_id "
        "FROM {}.users u "
        "JOIN {}.roles r ON u.role_id = r.role_id "
        "WHERE u.status = 'active' "
        "ORDER BY u.user_id"
    ).format(sql.Identifier(schema), sql.Identifier(schema))
    cur.execute(query)
    result: dict[str, list[int]] = defaultdict(list)
    for role_name, user_id in cur.fetchall():
        result[role_name].append(user_id)
    return result


def truncate_tables(cur: Any, schema: str) -> None:
    stmt = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
        sql.SQL(", ").join(
            sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table_name))
            for table_name in TRUNCATE_ORDER
        )
    )
    cur.execute(stmt)


def seed_reference_tables(cur: Any, schema: str) -> tuple[dict[str, int], dict[tuple[str, str], int], dict[str, int]]:
    role_rows = [{"role_name": name, "description": description} for name, description in ROLE_SPECS]
    zone_rows = [
        {"zone_name": z["zone_name"], "district_name": z["district_name"], "description": z["description"]}
        for z in ZONE_SPECS
    ]
    asset_type_rows = [{"type_name": name, "description": description} for name, description in ASSET_TYPE_SPECS]

    bulk_insert(cur, schema, "roles", role_rows)
    bulk_insert(cur, schema, "zones", zone_rows)
    bulk_insert(cur, schema, "asset_types", asset_type_rows)

    role_map = fetch_id_map(cur, schema, "roles", "role_name", "role_id")
    zone_map = fetch_zone_map(cur, schema)
    asset_type_map = fetch_id_map(cur, schema, "asset_types", "type_name", "asset_type_id")
    return role_map, zone_map, asset_type_map


def generate_users(rng: random.Random, role_map: dict[str, int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    email_counter = 1
    for role_name, count in ROLE_DISTRIBUTION.items():
        role_id = role_map[role_name]
        for idx in range(count):
            first_name = rng.choice(FIRST_NAMES)
            last_name = rng.choice(LAST_NAMES)
            created_at = random_datetime(rng, datetime(2024, 1, 1, 0, 0, 0), datetime(2025, 12, 31, 23, 59, 59))
            status = "active" if idx == 0 else choose_status_by_weights(rng, USER_STATUS_WEIGHTS)
            rows.append(
                {
                    "role_id": role_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{first_name.lower()}.{last_name.lower()}{email_counter}@smartcity.local",
                    "phone_number": f"+374{rng.randint(91000000, 99999999)}",
                    "status": status,
                    "created_at": created_at,
                }
            )
            email_counter += 1
    return rows


def generate_assets(
    rng: random.Random,
    zone_map: dict[tuple[str, str], int],
    asset_type_map: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    runtime: dict[str, dict[str, Any]] = {}
    counters: defaultdict[tuple[str, str], int] = defaultdict(int)

    for zone in ZONE_SPECS:
        zone_id = zone_map[(zone["zone_name"], zone["district_name"])]
        z_code = zone_code(zone["zone_name"])
        weights = PROFILE_ASSET_WEIGHTS[zone["profile"]]
        for _ in range(zone["asset_count"]):
            asset_type_name = weighted_choice(rng, weights)
            counters[(asset_type_name, z_code)] += 1
            seq = counters[(asset_type_name, z_code)]
            installation_date = random_date(rng, INSTALLATION_START_DATE, INSTALLATION_END_DATE)
            status = choose_status_by_weights(rng, ASSET_STATUS_WEIGHTS)
            asset_name = f"{ASSET_TYPE_CODES[asset_type_name]}-{z_code}-{seq:04d}"
            latitude = round(zone["center_lat"] + rng.uniform(-0.0085, 0.0085), 6)
            longitude = round(zone["center_lon"] + rng.uniform(-0.0085, 0.0085), 6)
            row = {
                "zone_id": zone_id,
                "asset_type_id": asset_type_map[asset_type_name],
                "asset_name": asset_name,
                "latitude": latitude,
                "longitude": longitude,
                "installation_date": installation_date,
                "status": status,
            }
            rows.append(row)
            runtime[asset_name] = {
                "asset_name": asset_name,
                "asset_type_name": asset_type_name,
                "zone_id": zone_id,
                "zone_name": zone["zone_name"],
                "district_name": zone["district_name"],
                "zone_profile": zone["profile"],
                "transit_priority": zone["transit_priority"],
                "installation_date": installation_date,
                "status": status,
            }
    return rows, runtime


def generate_sensor_rows(
    rng: random.Random,
    asset_rows_by_id: list[tuple[int, str, str]],
    asset_runtime_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    sensor_rows: list[dict[str, Any]] = []

    for asset_id, asset_name, asset_status in asset_rows_by_id:
        if asset_status != "active":
            continue
        runtime = asset_runtime_by_name[asset_name]
        base_time = datetime.combine(runtime["installation_date"], time(8, 0, 0))
        for sensor_type in ASSET_SENSOR_MAP[runtime["asset_type_name"]]:
            cfg = SENSOR_LIBRARY[sensor_type]
            installed_at = base_time + timedelta(days=rng.randint(0, 21), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            sensor_rows.append(
                {
                    "asset_id": asset_id,
                    "sensor_type": sensor_type,
                    "measurement_unit": cfg["measurement_unit"],
                    "installed_at": installed_at,
                    "status": choose_status_by_weights(rng, SENSOR_STATUS_WEIGHTS),
                }
            )

    return sensor_rows


def generate_threshold_rows_from_inserted_sensors(
    fetched_sensors: list[tuple[int, int, str, datetime, str]],
    asset_name_by_id: dict[int, str],
    asset_runtime_by_name: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    threshold_rows: list[dict[str, Any]] = []
    sensor_runtime: dict[int, dict[str, Any]] = {}

    for sensor_id, asset_id, sensor_type, installed_at, sensor_status in fetched_sensors:
        asset_name = asset_name_by_id[asset_id]
        asset_runtime = asset_runtime_by_name[asset_name]
        cfg = SENSOR_LIBRARY[sensor_type]

        sensor_runtime[sensor_id] = {
            "sensor_id": sensor_id,
            "asset_id": asset_id,
            "asset_name": asset_name,
            "asset_type_name": asset_runtime["asset_type_name"],
            "zone_id": asset_runtime["zone_id"],
            "zone_name": asset_runtime["zone_name"],
            "zone_profile": asset_runtime["zone_profile"],
            "transit_priority": asset_runtime["transit_priority"],
            "sensor_type": sensor_type,
            "installed_at": installed_at,
            "sensor_status": sensor_status,
            "min_value": cfg["min"],
            "max_value": cfg["max"],
            "warning_level": cfg["warning"],
            "critical_level": cfg["critical"],
            "measurement_unit": cfg["measurement_unit"],
        }

        threshold_rows.append(
            {
                "sensor_id": sensor_id,
                "effective_from": installed_at,
                "min_value": cfg["min"],
                "max_value": cfg["max"],
                "warning_level": cfg["warning"],
                "critical_level": cfg["critical"],
            }
        )

    return threshold_rows, sensor_runtime


def generate_normal_reading(rng: random.Random, cfg: dict[str, Any]) -> float:
    midpoint = (cfg["min_value"] + cfg["max_value"]) / 2
    spread = max((cfg["max_value"] - cfg["min_value"]) / 6, 0.1)
    value = rng.gauss(midpoint, spread)
    value = clamp(value, cfg["min_value"] + 0.01, cfg["max_value"] - 0.01)
    return round(value, 4)


def generate_warning_reading(rng: random.Random, cfg: dict[str, Any]) -> float:
    return round(rng.uniform(cfg["warning_level"], cfg["critical_level"] - 0.01), 4)


def generate_critical_reading(rng: random.Random, cfg: dict[str, Any]) -> float:
    high = cfg["critical_level"] + max(0.1, (cfg["critical_level"] - cfg["warning_level"]) * 0.35)
    return round(rng.uniform(cfg["critical_level"], high), 4)


def generate_invalid_reading(rng: random.Random, cfg: dict[str, Any]) -> float:
    midpoint = (cfg["min_value"] + cfg["max_value"]) / 2
    factor = rng.choice([0.0, 1.75, 2.25, -0.25])
    return round(midpoint * factor, 4)


def unique_times_for_sensor(
    rng: random.Random,
    start: datetime,
    end: datetime,
    interval_hours: int,
    jitter_minutes: int = 15,
) -> list[datetime]:
    if start > end:
        return []

    timestamps: list[datetime] = []
    used: set[datetime] = set()
    current = start

    while current <= end:
        jitter = timedelta(minutes=rng.randint(-jitter_minutes, jitter_minutes))
        reading_time = current + jitter

        if reading_time < start:
            reading_time = start
        if reading_time > end:
            reading_time = end

        while reading_time in used:
            reading_time += timedelta(seconds=1)
            if reading_time > end:
                reading_time -= timedelta(seconds=2)

        used.add(reading_time)
        timestamps.append(reading_time)
        current += timedelta(hours=interval_hours)

    timestamps.sort()
    return timestamps


def generate_sensor_readings(
    rng: random.Random,
    sensor_runtime: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reading_rows: list[dict[str, Any]] = []
    abnormal_candidates: list[dict[str, Any]] = []

    for sensor_id, cfg in sensor_runtime.items():
        sensor_status = cfg["sensor_status"]
        if sensor_status in {"inactive", "maintenance"}:
            continue

        timestamps = unique_times_for_sensor(
            rng,
            READING_WINDOW_START,
            READING_WINDOW_END,
            READING_INTERVAL_HOURS,
            READING_TIME_JITTER_MINUTES,
        )

        quality_weights = FAULTY_SENSOR_QUALITY_WEIGHTS if sensor_status == "faulty" else ACTIVE_SENSOR_QUALITY_WEIGHTS
        quality_labels = list(quality_weights.keys())
        quality_values = list(quality_weights.values())

        for reading_time in timestamps:
            quality = rng.choices(quality_labels, weights=quality_values, k=1)[0]
            if quality == "normal":
                value = generate_normal_reading(rng, cfg)
            elif quality == "warning":
                value = generate_warning_reading(rng, cfg)
            elif quality == "critical":
                value = generate_critical_reading(rng, cfg)
            else:
                value = generate_invalid_reading(rng, cfg)
            reading_rows.append(
                {
                    "sensor_id": sensor_id,
                    "reading_value": value,
                    "reading_time": reading_time,
                    "quality_flag": quality,
                }
            )
            if quality != "normal":
                abnormal_candidates.append(
                    {
                        "sensor_id": sensor_id,
                        "asset_id": cfg["asset_id"],
                        "asset_name": cfg["asset_name"],
                        "asset_type_name": cfg["asset_type_name"],
                        "zone_id": cfg["zone_id"],
                        "zone_profile": cfg["zone_profile"],
                        "transit_priority": cfg["transit_priority"],
                        "sensor_type": cfg["sensor_type"],
                        "reading_time": reading_time,
                        "reading_value": value,
                        "quality_flag": quality,
                    }
                )

    reading_rows.sort(key=lambda r: (r["sensor_id"], r["reading_time"]))
    abnormal_candidates.sort(key=lambda r: r["reading_time"])
    return reading_rows, abnormal_candidates


def auto_incident_type(asset_type_name: str, sensor_type: str) -> str:
    mapping = {
        ("Water Pump Station", "pressure_sensor"): "Pump Pressure Anomaly",
        ("Water Pump Station", "flow_sensor"): "Pump Flow Irregularity",
        ("Water Pump Station", "vibration_sensor"): "Pump Vibration Alert",
        ("Water Pump Station", "water_level_sensor"): "Pump Station Water Level Alert",
        ("Water Pipeline Segment", "pressure_sensor"): "Pipeline Pressure Instability",
        ("Water Pipeline Segment", "flow_sensor"): "Possible Pipeline Leakage",
        ("Water Pipeline Segment", "pipeline_temperature_sensor"): "Pipeline Temperature Alert",
        ("Electrical Transformer Unit", "voltage_sensor"): "Voltage Instability",
        ("Electrical Transformer Unit", "current_sensor"): "Transformer Current Overload",
        ("Electrical Transformer Unit", "transformer_temperature_sensor"): "Transformer Overheating",
        ("Electrical Transformer Unit", "load_sensor"): "Transformer Load Spike",
        ("Street Lighting Unit", "voltage_sensor"): "Street Lighting Voltage Fault",
        ("Street Lighting Unit", "power_draw_sensor"): "Lighting Power Consumption Alert",
        ("Street Lighting Unit", "controller_temperature_sensor"): "Lighting Controller Overheating",
        ("Traffic Signal Controller", "cycle_delay_sensor"): "Signal Timing Delay",
        ("Traffic Signal Controller", "voltage_sensor"): "Traffic Controller Power Fault",
        ("Traffic Signal Controller", "controller_temperature_sensor"): "Traffic Controller Overheating",
        ("Roadside Traffic Sensor Hub", "traffic_volume_sensor"): "Traffic Volume Surge",
        ("Roadside Traffic Sensor Hub", "queue_length_sensor"): "Queue Overflow Alert",
        ("Roadside Traffic Sensor Hub", "occupancy_rate_sensor"): "Congestion Density Alert",
        ("Roadside Traffic Sensor Hub", "device_temperature_sensor"): "Traffic Sensor Hub Overheating",
        ("Waste Collection Unit", "fill_level_sensor"): "Waste Overflow Alert",
        ("Waste Collection Unit", "internal_temperature_sensor"): "Waste Unit Temperature Alert",
        ("Waste Collection Unit", "gas_level_sensor"): "Gas Accumulation Alert",
        ("Environmental Monitoring Station", "air_temperature_sensor"): "Air Temperature Alert",
        ("Environmental Monitoring Station", "humidity_sensor"): "Humidity Anomaly",
        ("Environmental Monitoring Station", "pm25_sensor"): "PM2.5 Pollution Alert",
        ("Environmental Monitoring Station", "co2_sensor"): "CO2 Concentration Alert",
    }
    return mapping.get((asset_type_name, sensor_type), "Sensor-Based Incident")


def manual_incident_type(rng: random.Random, asset_type_name: str) -> str:
    mapping = {
        "Water Pump Station": ["Pump Station Mechanical Fault Report", "Control Panel Fault Report", "Pressure Loss Field Report"],
        "Water Pipeline Segment": ["Possible Leakage Field Report", "Pipeline Pressure Complaint", "Water Service Irregularity Report"],
        "Electrical Transformer Unit": ["Transformer Fault Report", "Power Instability Field Report", "Electrical Equipment Inspection Alert"],
        "Street Lighting Unit": ["Street Lighting Outage Report", "Lighting Control Fault Report", "Lighting Inspection Alert"],
        "Traffic Signal Controller": ["Intersection Signal Fault Report", "Traffic Timing Complaint", "Controller Inspection Alert"],
        "Roadside Traffic Sensor Hub": ["Traffic Monitoring Fault Report", "Congestion Observation Report", "Roadside Hub Communication Fault"],
        "Waste Collection Unit": ["Overflow Complaint", "Waste Collection Delay Report", "Waste Unit Condition Alert"],
        "Environmental Monitoring Station": ["Air Quality Review Alert", "Station Communication Fault Report", "Environmental Inspection Notice"],
    }
    return rng.choice(mapping[asset_type_name])


def determine_auto_severity(rng: random.Random, quality_flag: str, asset_type_name: str) -> str:
    if quality_flag == "critical":
        if asset_type_name in {"Electrical Transformer Unit", "Traffic Signal Controller", "Water Pump Station"}:
            return rng.choices(["high", "critical"], weights=[0.35, 0.65], k=1)[0]
        return rng.choices(["medium", "high", "critical"], weights=[0.10, 0.45, 0.45], k=1)[0]
    if quality_flag == "warning":
        if asset_type_name in {"Roadside Traffic Sensor Hub", "Street Lighting Unit"}:
            return rng.choices(["medium", "high"], weights=[0.55, 0.45], k=1)[0]
        return rng.choices(["low", "medium", "high"], weights=[0.20, 0.60, 0.20], k=1)[0]
    return rng.choices(["low", "medium"], weights=[0.80, 0.20], k=1)[0]


def generate_incidents(
    rng: random.Random,
    abnormal_candidates: list[dict[str, Any]],
    active_asset_rows_by_id: list[tuple[int, str]],
    asset_runtime_by_name: dict[str, dict[str, Any]],
    asset_name_by_id: dict[int, str],
) -> list[dict[str, Any]]:
    target_manual = int(TARGET_INCIDENTS * MANUAL_INCIDENT_SHARE)
    target_auto = TARGET_INCIDENTS - target_manual

    auto_pool = abnormal_candidates.copy()
    rng.shuffle(auto_pool)
    auto_selected = auto_pool[: min(target_auto, len(auto_pool))]

    incidents: list[dict[str, Any]] = []

    for item in auto_selected:
        status = rng.choices(["detected", "in_progress", "resolved", "closed"], weights=[0.12, 0.20, 0.42, 0.26], k=1)[0]
        detected_at = item["reading_time"] + timedelta(minutes=rng.randint(1, 30))
        resolved_at = None
        if status in {"resolved", "closed"}:
            resolved_at = detected_at + timedelta(hours=rng.randint(2, 120))
        incidents.append(
            {
                "asset_id": item["asset_id"],
                "sensor_id": item["sensor_id"],
                "incident_type": auto_incident_type(item["asset_type_name"], item["sensor_type"]),
                "severity": determine_auto_severity(rng, item["quality_flag"], item["asset_type_name"]),
                "status": status,
                "description": f"Automatically detected from {item['sensor_type']} with reading {item['reading_value']}",
                "detected_at": detected_at,
                "resolved_at": resolved_at,
            }
        )

    asset_choices = [asset_id for asset_id, _ in active_asset_rows_by_id]
    weights = []
    for asset_id, asset_name in active_asset_rows_by_id:
        asset_info = asset_runtime_by_name[asset_name]
        base_weight = 1.0
        if asset_info["zone_profile"] in {"transit", "industrial", "logistics"}:
            base_weight += 0.35
        if asset_info["asset_type_name"] in {"Electrical Transformer Unit", "Traffic Signal Controller", "Water Pipeline Segment"}:
            base_weight += 0.25
        weights.append(base_weight)

    for _ in range(target_manual):
        asset_id = rng.choices(asset_choices, weights=weights, k=1)[0]
        asset_name = asset_name_by_id[asset_id]
        asset_info = asset_runtime_by_name[asset_name]
        detected_at = random_datetime(rng, READING_WINDOW_START, READING_WINDOW_END)
        status = rng.choices(["detected", "in_progress", "resolved", "closed"], weights=[0.15, 0.25, 0.38, 0.22], k=1)[0]
        resolved_at = None
        if status in {"resolved", "closed"}:
            resolved_at = detected_at + timedelta(hours=rng.randint(4, 160))
        severity = rng.choices(["low", "medium", "high", "critical"], weights=[0.28, 0.42, 0.22, 0.08], k=1)[0]
        incidents.append(
            {
                "asset_id": asset_id,
                "sensor_id": None,
                "incident_type": manual_incident_type(rng, asset_info["asset_type_name"]),
                "severity": severity,
                "status": status,
                "description": "Manually reported by field inspection or operational observation.",
                "detected_at": detected_at,
                "resolved_at": resolved_at,
            }
        )

    incidents.sort(key=lambda x: x["detected_at"])
    return incidents[:TARGET_INCIDENTS]


def generate_work_orders(
    rng: random.Random,
    inserted_incidents: list[tuple[int, int, str, str, datetime, datetime | None]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for incident_id, asset_id, incident_type, severity, detected_at, resolved_at in inserted_incidents:
        if rng.random() > WORK_ORDER_PROBABILITY[severity]:
            continue
        status = rng.choices(["open", "assigned", "in_progress", "completed", "closed", "cancelled"], weights=[0.12, 0.18, 0.26, 0.22, 0.17, 0.05], k=1)[0]
        opened_at = detected_at + timedelta(minutes=rng.randint(15, 180))
        closed_at = None
        resolution_summary = None
        if status in {"completed", "closed", "cancelled"}:
            base_finish = resolved_at if resolved_at is not None and resolved_at > opened_at else opened_at + timedelta(hours=rng.randint(4, 96))
            closed_at = base_finish + timedelta(minutes=rng.randint(0, 180))
            if status != "cancelled":
                resolution_summary = rng.choice([
                    "Field repair completed and system stabilized.",
                    "Component adjusted and returned to service.",
                    "Operational issue addressed and verified.",
                    "Affected equipment serviced and status normalized.",
                ])
            else:
                resolution_summary = "Work order cancelled after operational review."
        rows.append(
            {
                "incident_id": incident_id,
                "asset_id": asset_id,
                "priority": severity,
                "status": status,
                "problem_description": f"Work order created for incident: {incident_type}.",
                "resolution_summary": resolution_summary,
                "opened_at": opened_at,
                "closed_at": closed_at,
            }
        )
    return rows


def generate_work_order_assignments(
    rng: random.Random,
    inserted_work_orders: list[tuple[int, str, datetime, datetime | None]],
    active_users_by_role: dict[str, list[int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    supervisors = active_users_by_role["Maintenance Supervisor"]
    technicians = active_users_by_role["Maintenance Technician"]

    for work_order_id, work_order_status, opened_at, closed_at in inserted_work_orders:
        supervisor_id = rng.choice(supervisors)
        rows.append(
            build_assignment_row(
                rng,
                work_order_id,
                supervisor_id,
                opened_at + timedelta(minutes=rng.randint(0, 60)),
                closed_at,
                "Supervisor",
                work_order_status,
            )
        )

        tech_count = rng.choices([1, 2, 3], weights=[0.48, 0.36, 0.16], k=1)[0]
        chosen_techs = rng.sample(technicians, tech_count)
        for index, technician_id in enumerate(chosen_techs):
            role_name = "Lead Technician" if index == 0 else "Assigned Technician"
            rows.append(
                build_assignment_row(
                    rng,
                    work_order_id,
                    technician_id,
                    opened_at + timedelta(minutes=rng.randint(5, 180)),
                    closed_at,
                    role_name,
                    work_order_status,
                )
            )
    return rows


def build_assignment_row(
    rng: random.Random,
    work_order_id: int,
    user_id: int,
    assigned_at: datetime,
    closed_at: datetime | None,
    assignment_role: str,
    work_order_status: str,
) -> dict[str, Any]:
    if work_order_status in {"completed", "closed"}:
        assignment_status = "completed"
        released_at = (closed_at or assigned_at) + timedelta(minutes=rng.randint(0, 120))
    elif work_order_status == "cancelled":
        assignment_status = "cancelled"
        released_at = assigned_at + timedelta(hours=rng.randint(1, 8))
    elif work_order_status in {"assigned", "open"}:
        assignment_status = "assigned"
        released_at = None
    else:
        assignment_status = "active"
        released_at = None
    return {
        "work_order_id": work_order_id,
        "user_id": user_id,
        "assigned_at": assigned_at,
        "released_at": released_at,
        "assignment_role": assignment_role,
        "assignment_status": assignment_status,
    }


def generate_emergency_units(rng: random.Random) -> list[dict[str, Any]]:
    unit_types = ["Technical Response Unit", "Water Response Unit", "Electrical Response Unit", "Traffic Response Unit", "Environmental Response Unit"]
    weighted_statuses = ["available", "dispatched", "busy", "maintenance", "out_of_service"]
    status_weights = [0.72, 0.08, 0.10, 0.06, 0.04]
    rows: list[dict[str, Any]] = []
    zone_cycle = ZONE_SPECS.copy()

    for idx, unit_type in enumerate(unit_types, start=1):
        zone = zone_cycle[(idx - 1) % len(zone_cycle)]
        rows.append(
            {
                "unit_name": f"{unit_type.split()[0]} Unit {idx:02d}",
                "unit_type": unit_type,
                "base_location": f"{zone['district_name']} Operations Base",
                "status": "available",
            }
        )

    for idx in range(len(unit_types) + 1, TARGET_EMERGENCY_UNITS + 1):
        zone = zone_cycle[(idx - 1) % len(zone_cycle)]
        unit_type = rng.choices(unit_types, weights=[0.28, 0.18, 0.20, 0.22, 0.12], k=1)[0]
        status = rng.choices(weighted_statuses, weights=status_weights, k=1)[0]
        rows.append(
            {
                "unit_name": f"{unit_type.split()[0]} Unit {idx:02d}",
                "unit_type": unit_type,
                "base_location": f"{zone['district_name']} Operations Base",
                "status": status,
            }
        )
    return rows


def generate_transit_routes_and_vehicle_data(rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
    route_rows: list[dict[str, Any]] = []
    vehicle_rows: list[dict[str, Any]] = []
    route_to_zone_names: dict[str, list[str]] = {}

    zone_names = [z["zone_name"] for z in ZONE_SPECS]
    zone_weights = [z["transit_priority"] + 0.03 for z in ZONE_SPECS]

    for route_num in range(1, TARGET_TRANSIT_ROUTES + 1):
        route_name = f"City Route {route_num:02d}"
        served_count = rng.randint(3, 5)
        chosen = weighted_sample_without_replacement(rng, zone_names, zone_weights, served_count)
        route_to_zone_names[route_name] = sorted(chosen)
        route_rows.append(
            {
                "route_name": route_name,
                "route_code": f"R{route_num:03d}",
                "status": rng.choices(["active", "delayed", "suspended", "inactive"], weights=[0.80, 0.08, 0.04, 0.08], k=1)[0],
            }
        )

    vehicle_types = ["Bus", "Minibus", "Trolleybus"]
    vehicle_weights = [0.55, 0.30, 0.15]

    for vehicle_num in range(1, TARGET_TRANSIT_VEHICLES + 1):
        vehicle_type = rng.choices(vehicle_types, weights=vehicle_weights, k=1)[0]
        prefix = {"Bus": "BUS", "Minibus": "MB", "Trolleybus": "TB"}[vehicle_type]
        vehicle_rows.append(
            {
                "vehicle_number": f"{prefix}-{vehicle_num:03d}",
                "vehicle_type": vehicle_type,
                "status": rng.choices(["active", "delayed", "maintenance", "out_of_service"], weights=[0.78, 0.08, 0.08, 0.06], k=1)[0],
            }
        )

    return route_rows, vehicle_rows, route_to_zone_names


def fetch_inserted_incidents(cur: Any, schema: str) -> list[tuple[int, int, str, str, datetime, datetime | None]]:
    query = sql.SQL(
        "SELECT incident_id, asset_id, incident_type, severity, detected_at, resolved_at FROM {}.incidents ORDER BY incident_id"
    ).format(sql.Identifier(schema))
    cur.execute(query)
    return cur.fetchall()


def fetch_inserted_work_orders(cur: Any, schema: str) -> list[tuple[int, str, datetime, datetime | None]]:
    query = sql.SQL(
        "SELECT work_order_id, status, opened_at, closed_at "
        "FROM {}.maintenance_work_orders ORDER BY work_order_id"
    ).format(sql.Identifier(schema))
    cur.execute(query)
    return cur.fetchall()


def fetch_id_by_name(cur: Any, schema: str, table_name: str, name_col: str, id_col: str) -> dict[str, int]:
    query = sql.SQL("SELECT {}, {} FROM {}.{}").format(
        sql.Identifier(name_col),
        sql.Identifier(id_col),
        sql.Identifier(schema),
        sql.Identifier(table_name),
    )
    cur.execute(query)
    return {name: id_value for name, id_value in cur.fetchall()}


def generate_dispatch_records(
    rng: random.Random,
    inserted_incidents: list[tuple[int, int, str, str, datetime, datetime | None]],
    incident_runtime: dict[int, dict[str, Any]],
    active_users_by_role: dict[str, list[int]],
    available_unit_ids_by_type: dict[str, list[int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dispatchers = active_users_by_role["Dispatcher"]

    for incident_id, _asset_id, _incident_type, severity, detected_at, resolved_at in inserted_incidents:
        runtime = incident_runtime[incident_id]
        asset_type_name = runtime["asset_type_name"]
        zone_profile = runtime["zone_profile"]

        base_prob = {"critical": 0.78, "high": 0.42, "medium": 0.12, "low": 0.02}[severity]
        if asset_type_name in {"Traffic Signal Controller", "Roadside Traffic Sensor Hub", "Electrical Transformer Unit", "Water Pipeline Segment"}:
            base_prob += 0.08
        if zone_profile in {"transit", "central", "logistics"}:
            base_prob += 0.05
        base_prob = min(base_prob, 0.92)

        if rng.random() > base_prob:
            continue

        target_unit_type = UNIT_TYPE_BY_ASSET_TYPE[asset_type_name]
        available_units = available_unit_ids_by_type.get(target_unit_type, [])
        if not available_units:
            continue

        dispatch_time = detected_at + timedelta(minutes=rng.randint(2, 45))
        arrival_time = dispatch_time + timedelta(minutes=rng.randint(6, 55))

        if resolved_at and resolved_at > arrival_time:
            completion_time = resolved_at + timedelta(minutes=rng.randint(0, 90))
            status = rng.choices(["completed", "arrived"], weights=[0.88, 0.12], k=1)[0]
            if status == "arrived":
                completion_time = None
        else:
            status = rng.choices(["dispatched", "en_route", "arrived", "completed", "cancelled"], weights=[0.10, 0.22, 0.30, 0.32, 0.06], k=1)[0]
            if status == "cancelled":
                arrival_time = None
                completion_time = None
            elif status in {"dispatched", "en_route"}:
                arrival_time = None
                completion_time = None
            elif status == "arrived":
                completion_time = None
            else:
                completion_time = arrival_time + timedelta(minutes=rng.randint(15, 180))

        rows.append(
            {
                "incident_id": incident_id,
                "emergency_unit_id": rng.choice(available_units),
                "dispatcher_user_id": rng.choice(dispatchers),
                "dispatch_time": dispatch_time,
                "arrival_time": arrival_time,
                "completion_time": completion_time,
                "status": status,
            }
        )
    return rows


def build_transit_runtime(
    route_name_to_id: dict[str, int],
    vehicle_number_to_id: dict[str, int],
    route_to_zone_names: dict[str, list[str]],
    vehicle_rows: list[dict[str, Any]],
) -> tuple[dict[int, list[int]], dict[int, list[str]]]:
    route_id_to_zone_names: dict[int, list[str]] = {}
    for route_name, zone_names in route_to_zone_names.items():
        route_id_to_zone_names[route_name_to_id[route_name]] = zone_names

    route_ids = list(route_name_to_id.values())
    route_id_to_vehicle_ids: dict[int, list[int]] = defaultdict(list)
    for idx, vehicle_row in enumerate(vehicle_rows):
        vehicle_id = vehicle_number_to_id[vehicle_row["vehicle_number"]]
        route_id = route_ids[idx % len(route_ids)]
        route_id_to_vehicle_ids[route_id].append(vehicle_id)

    return route_id_to_vehicle_ids, route_id_to_zone_names


def generate_incident_transit_impacts(
    rng: random.Random,
    inserted_incidents: list[tuple[int, int, str, str, datetime, datetime | None]],
    incident_runtime: dict[int, dict[str, Any]],
    route_id_to_vehicle_ids: dict[int, list[int]],
    route_id_to_zone_names: dict[int, list[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    impact_types = ["delay", "reroute", "service_disruption", "stop_bypass", "traffic_congestion"]

    for incident_id, _asset_id, _incident_type, severity, detected_at, resolved_at in inserted_incidents:
        runtime = incident_runtime[incident_id]
        asset_type_name = runtime["asset_type_name"]
        zone_name = runtime["zone_name"]
        transit_priority = runtime["transit_priority"]

        prob = {"critical": 0.42, "high": 0.28, "medium": 0.16, "low": 0.05}[severity]
        if asset_type_name in {"Traffic Signal Controller", "Roadside Traffic Sensor Hub", "Street Lighting Unit", "Electrical Transformer Unit", "Water Pipeline Segment"}:
            prob += 0.12
        prob += transit_priority * 0.75
        prob = min(prob, 0.85)
        if rng.random() > prob:
            continue

        candidate_route_ids = [route_id for route_id, zone_names in route_id_to_zone_names.items() if zone_name in zone_names]
        if not candidate_route_ids:
            continue
        route_id = rng.choice(candidate_route_ids)
        vehicle_candidates = route_id_to_vehicle_ids.get(route_id)
        if not vehicle_candidates:
            continue

        if severity == "critical":
            delay_minutes = rng.randint(25, 90)
        elif severity == "high":
            delay_minutes = rng.randint(15, 60)
        elif severity == "medium":
            delay_minutes = rng.randint(5, 35)
        else:
            delay_minutes = rng.randint(0, 15)

        recorded_at = detected_at + timedelta(minutes=rng.randint(5, 75))
        if resolved_at and resolved_at > recorded_at:
            status = rng.choices(["resolved", "logged", "active"], weights=[0.55, 0.25, 0.20], k=1)[0]
        else:
            status = rng.choices(["active", "logged", "resolved"], weights=[0.52, 0.32, 0.16], k=1)[0]

        rows.append(
            {
                "incident_id": incident_id,
                "route_id": route_id,
                "vehicle_id": rng.choice(vehicle_candidates),
                "impact_type": rng.choice(impact_types),
                "delay_minutes": delay_minutes,
                "recorded_at": recorded_at,
                "status": status,
            }
        )
    return rows


def update_asset_statuses(cur: Any, schema: str) -> None:
    maintenance_stmt = sql.SQL(
        """
        UPDATE {}.assets a
        SET status = 'under_maintenance'
        WHERE a.status = 'active'
          AND EXISTS (
              SELECT 1
              FROM {}.maintenance_work_orders w
              WHERE w.asset_id = a.asset_id
                AND w.status IN ('open', 'assigned', 'in_progress')
          )
        """
    ).format(sql.Identifier(schema), sql.Identifier(schema))
    cur.execute(maintenance_stmt)

    incident_stmt = sql.SQL(
        """
        UPDATE {}.assets a
        SET status = 'under_incident'
        WHERE a.status = 'active'
          AND EXISTS (
              SELECT 1
              FROM {}.incidents i
              WHERE i.asset_id = a.asset_id
                AND i.status IN ('detected', 'in_progress')
          )
        """
    ).format(sql.Identifier(schema), sql.Identifier(schema))
    cur.execute(incident_stmt)


def print_counts(cur: Any, schema: str) -> None:
    print("\nInserted row counts:")
    for table_name in TABLE_ORDER:
        query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table_name))
        cur.execute(query)
        count = cur.fetchone()[0]
        print(f"  {table_name}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and load Smart City synthetic data directly into PostgreSQL.")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--schema", default="smart_city")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--truncate", action="store_true", help="Truncate existing Smart City tables before loading new data.")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            if args.truncate:
                truncate_tables(cur, args.schema)

            role_map, zone_map, asset_type_map = seed_reference_tables(cur, args.schema)

            user_rows = generate_users(rng, role_map)
            bulk_insert(cur, args.schema, "users", user_rows)
            active_users_by_role = fetch_active_users_by_role(cur, args.schema)

            asset_rows, asset_runtime_by_name = generate_assets(rng, zone_map, asset_type_map)
            bulk_insert(cur, args.schema, "assets", asset_rows)
            asset_rows_by_id = fetch_assets(cur, args.schema)
            asset_name_by_id = {asset_id: asset_name for asset_id, asset_name, _status in asset_rows_by_id}
            active_asset_rows = [(asset_id, asset_name) for asset_id, asset_name, status in asset_rows_by_id if status == "active"]

            sensor_rows = generate_sensor_rows(rng, asset_rows_by_id, asset_runtime_by_name)
            bulk_insert(cur, args.schema, "sensors", sensor_rows)
            fetched_sensors = fetch_sensors(cur, args.schema)

            threshold_rows, sensor_runtime = generate_threshold_rows_from_inserted_sensors(
                fetched_sensors, asset_name_by_id, asset_runtime_by_name
            )
            bulk_insert(cur, args.schema, "threshold_rules", threshold_rows)

            reading_rows, abnormal_candidates = generate_sensor_readings(rng, sensor_runtime)
            bulk_insert(cur, args.schema, "sensor_readings", reading_rows)

            incident_rows = generate_incidents(rng, abnormal_candidates, active_asset_rows, asset_runtime_by_name, asset_name_by_id)
            bulk_insert(cur, args.schema, "incidents", incident_rows)
            inserted_incidents = fetch_inserted_incidents(cur, args.schema)

            incident_runtime: dict[int, dict[str, Any]] = {}
            for incident_id, asset_id, incident_type, severity, detected_at, resolved_at in inserted_incidents:
                asset_name = asset_name_by_id[asset_id]
                base = asset_runtime_by_name[asset_name]
                incident_runtime[incident_id] = {
                    "asset_type_name": base["asset_type_name"],
                    "zone_name": base["zone_name"],
                    "zone_profile": base["zone_profile"],
                    "transit_priority": base["transit_priority"],
                    "incident_type": incident_type,
                    "severity": severity,
                    "detected_at": detected_at,
                    "resolved_at": resolved_at,
                }

            work_order_rows = generate_work_orders(rng, inserted_incidents)
            bulk_insert(cur, args.schema, "maintenance_work_orders", work_order_rows)
            inserted_work_orders = fetch_inserted_work_orders(cur, args.schema)

            assignment_rows = generate_work_order_assignments(rng, inserted_work_orders, active_users_by_role)
            bulk_insert(cur, args.schema, "work_order_assignments", assignment_rows)

            emergency_unit_rows = generate_emergency_units(rng)
            bulk_insert(cur, args.schema, "emergency_units", emergency_unit_rows)
            cur.execute(
                sql.SQL(
                    "SELECT emergency_unit_id, unit_type FROM {}.emergency_units WHERE status = 'available' ORDER BY emergency_unit_id"
                ).format(sql.Identifier(args.schema))
            )
            available_unit_ids_by_type: dict[str, list[int]] = defaultdict(list)
            for unit_id, unit_type in cur.fetchall():
                available_unit_ids_by_type[unit_type].append(unit_id)

            dispatch_rows = generate_dispatch_records(rng, inserted_incidents, incident_runtime, active_users_by_role, available_unit_ids_by_type)
            bulk_insert(cur, args.schema, "dispatch_records", dispatch_rows)

            route_rows, vehicle_rows, route_to_zone_names = generate_transit_routes_and_vehicle_data(rng)
            bulk_insert(cur, args.schema, "transit_routes", route_rows)
            bulk_insert(cur, args.schema, "transit_vehicles", vehicle_rows)

            route_name_to_id = fetch_id_by_name(cur, args.schema, "transit_routes", "route_name", "route_id")
            vehicle_number_to_id = fetch_id_by_name(cur, args.schema, "transit_vehicles", "vehicle_number", "vehicle_id")
            route_id_to_vehicle_ids, route_id_to_zone_names = build_transit_runtime(route_name_to_id, vehicle_number_to_id, route_to_zone_names, vehicle_rows)

            impact_rows = generate_incident_transit_impacts(rng, inserted_incidents, incident_runtime, route_id_to_vehicle_ids, route_id_to_zone_names)
            bulk_insert(cur, args.schema, "incident_transit_impacts", impact_rows)

            update_asset_statuses(cur, args.schema)

            conn.commit()
            print_counts(cur, args.schema)
            print("\nSynthetic data generation and direct PostgreSQL load completed successfully.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
