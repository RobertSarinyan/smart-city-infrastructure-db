from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2 import sql


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

PRIMARY_KEY_COLUMN = {
    "roles": "role_id",
    "zones": "zone_id",
    "asset_types": "asset_type_id",
    "users": "user_id",
    "assets": "asset_id",
    "sensors": "sensor_id",
    "threshold_rules": "threshold_rule_id",
    "sensor_readings": "reading_id",
    "incidents": "incident_id",
    "maintenance_work_orders": "work_order_id",
    "work_order_assignments": "assignment_id",
    "emergency_units": "emergency_unit_id",
    "dispatch_records": "dispatch_id",
    "transit_routes": "route_id",
    "transit_vehicles": "vehicle_id",
    "incident_transit_impacts": "impact_id",
}

ORDER_BY = {
    "roles": ["role_id"],
    "zones": ["zone_id"],
    "asset_types": ["asset_type_id"],
    "users": ["user_id"],
    "assets": ["asset_id"],
    "sensors": ["sensor_id"],
    "threshold_rules": ["threshold_rule_id"],
    "sensor_readings": ["reading_id"],
    "incidents": ["incident_id"],
    "maintenance_work_orders": ["work_order_id"],
    "work_order_assignments": ["assignment_id"],
    "emergency_units": ["emergency_unit_id"],
    "dispatch_records": ["dispatch_id"],
    "transit_routes": ["route_id"],
    "transit_vehicles": ["vehicle_id"],
    "incident_transit_impacts": ["impact_id"],
}

IDENTITY_TABLES = set(TABLE_ORDER)


def ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def qualified_name(schema: str, table: str) -> str:
    return f"{ident(schema)}.{ident(table)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export populated Smart City data to a rerunnable populate_data.sql script."
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--schema", default="smart_city")
    parser.add_argument(
        "--output",
        default="populate_data.sql",
        help="Path of the generated SQL file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="How many rows to place in each INSERT statement.",
    )
    parser.add_argument(
        "--skip-truncate",
        action="store_true",
        help="Do not include a TRUNCATE section at the top of the exported SQL script.",
    )
    return parser.parse_args()


def fetch_table_columns(cur: Any, schema: str, table: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    columns = [row[0] for row in cur.fetchall()]
    if not columns:
        raise ValueError(f"Table {schema}.{table} does not exist or has no columns.")
    return columns


def fetch_rows(cur: Any, schema: str, table: str, order_by: list[str]) -> list[tuple[Any, ...]]:
    query = sql.SQL("SELECT * FROM {}.{} ORDER BY {}") .format(
        sql.Identifier(schema),
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(col) for col in order_by),
    )
    cur.execute(query)
    return cur.fetchall()


def batched(rows: list[tuple[Any, ...]], batch_size: int) -> Iterable[list[tuple[Any, ...]]]:
    for i in range(0, len(rows), batch_size):
        yield rows[i:i + batch_size]


def build_insert_statement(
    cur: Any,
    schema: str,
    table: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
    batch_size: int,
) -> str:
    if not rows:
        return f"-- {table}: 0 rows\n\n"

    qualified = qualified_name(schema, table)
    column_sql = ", ".join(ident(col) for col in columns)
    override_sql = " OVERRIDING SYSTEM VALUE" if table in IDENTITY_TABLES else ""
    placeholder_sql = "(" + ", ".join(["%s"] * len(columns)) + ")"

    parts: list[str] = [f"-- {table}: {len(rows)} rows\n"]

    for chunk in batched(rows, batch_size):
        values_sql = ",\n".join(
            cur.mogrify(placeholder_sql, row).decode("utf-8")
            for row in chunk
        )
        statement = (
            f"INSERT INTO {qualified} ({column_sql}){override_sql} VALUES\n"
            f"{values_sql};\n\n"
        )
        parts.append(statement)

    return "".join(parts)


def build_truncate_statement(schema: str) -> str:
    qualified_tables = ",\n    ".join(
        qualified_name(schema, table_name)
        for table_name in reversed(TABLE_ORDER)
    )
    return (
        "TRUNCATE TABLE\n    "
        f"{qualified_tables}\n"
        "RESTART IDENTITY CASCADE;\n\n"
    )


def build_sequence_reset_statement(schema: str, table: str, pk_column: str) -> str:
    qualified = qualified_name(schema, table)
    table_literal = f"'{schema}.{table}'"
    column_literal = f"'{pk_column}'"
    return (
        "SELECT setval(\n"
        f"    pg_get_serial_sequence({table_literal}, {column_literal}),\n"
        f"    COALESCE((SELECT MAX({ident(pk_column)}) FROM {qualified}), 1),\n"
        f"    (SELECT COUNT(*) > 0 FROM {qualified})\n"
        ");\n"
    )


def ensure_schema_exists(cur: Any, schema: str) -> None:
    cur.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
        (schema,),
    )
    if cur.fetchone() is None:
        raise ValueError(f"Schema '{schema}' does not exist in the selected database.")


def export_sql(args: argparse.Namespace) -> Path:
    output_path = Path(args.output).resolve()

    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )

    try:
        with conn.cursor() as cur:
            ensure_schema_exists(cur, args.schema)

            with output_path.open("w", encoding="utf-8") as f:
                f.write("-- Generated by write_sql.py\n")
                f.write("BEGIN;\n\n")
                f.write(f"SET search_path TO {ident(args.schema)}, public;\n\n")

                if not args.skip_truncate:
                    f.write(build_truncate_statement(args.schema))

                for table in TABLE_ORDER:
                    columns = fetch_table_columns(cur, args.schema, table)
                    rows = fetch_rows(cur, args.schema, table, ORDER_BY[table])
                    f.write(build_insert_statement(cur, args.schema, table, columns, rows, args.batch_size))

                f.write("-- Reset identity sequences to the current maximum IDs\n")
                for table in TABLE_ORDER:
                    f.write(build_sequence_reset_statement(args.schema, table, PRIMARY_KEY_COLUMN[table]))
                f.write("\nCOMMIT;\n")

        return output_path
    finally:
        conn.close()


def main() -> None:
    args = parse_args()
    output_path = export_sql(args)
    print(f"SQL export completed successfully: {output_path}")


if __name__ == "__main__":
    main()
