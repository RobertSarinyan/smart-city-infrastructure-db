# Smart City Infrastructure Management DBMS — Project Overview

## 1. Project Purpose

The **Smart City Infrastructure Management DBMS** is a PostgreSQL-based database project designed to model how a city can monitor, maintain, and analyze its infrastructure operations. The system focuses on infrastructure assets, IoT-style sensors, sensor readings, incidents, maintenance work orders, emergency dispatching, and transit-related disruptions.

The main goal of the project is to show how a relational database can support both:

- **Operational workflows**, such as registering assets, recording sensor readings, creating incidents, assigning maintenance work, and dispatching emergency units.
- **Analytical reporting**, such as identifying high-risk zones, frequently failing asset types, abnormal sensor behavior, maintenance workload, and emergency response performance.

The project was developed as part of a Database Systems course and demonstrates database design, SQL reporting, data generation, indexing, triggers, stored functions, and documentation.

---

## 2. System Domain

The system represents a simplified smart city infrastructure environment. In such a system, city operators need to track the condition of infrastructure assets across different zones of the city.

Examples of infrastructure assets include:

- Traffic lights
- Water infrastructure
- Electrical units
- Waste management infrastructure
- Transit-related infrastructure
- Other monitored city assets

Each asset can have one or more sensors attached to it. These sensors produce readings over time, and readings can be compared against threshold rules to detect abnormal conditions. When a problem is detected, the system can track it as an incident and optionally connect it to maintenance work orders, emergency dispatch records, or transit impacts.

---

## 3. Main Database Entities

The database is organized around several core entity groups.

### Users and Roles

The system includes users such as administrators, operators, technicians, dispatch personnel, and emergency response staff. Roles are used to classify users and support responsibility tracking.

Main tables:

- `users`
- `roles`

### Infrastructure Assets

Assets represent physical infrastructure components located across city zones. Each asset belongs to a specific zone and asset type.

Main tables:

- `zones`
- `asset_types`
- `assets`

### Sensors and Sensor Readings

Sensors are attached to assets and produce time-based readings. Sensor readings are one of the largest parts of the database because they represent continuous monitoring data.

Main tables:

- `sensors`
- `sensor_readings`
- `threshold_rules`

### Incidents

Incidents represent abnormal events detected manually or through sensor-related conditions. They are connected to assets and, when relevant, sensors.

Main table:

- `incidents`

### Maintenance Work Orders

Maintenance work orders represent repair or inspection tasks created in response to asset conditions or incidents. Assignments connect work orders to responsible users or technicians.

Main tables:

- `maintenance_work_orders`
- `work_order_assignments`

### Emergency Dispatch

Emergency dispatch records represent cases where emergency units are sent to handle serious incidents.

Main tables:

- `emergency_units`
- `dispatch_records`

### Transit Impact

Some infrastructure incidents may affect transit routes or vehicles. The database includes transit-related tables to track these disruptions.

Main tables:

- `transit_routes`
- `transit_vehicles`
- `incident_transit_impacts`

---

## 4. Database Design Approach

The database follows a normalized relational design. The goal was to avoid unnecessary duplication, preserve data consistency, and make the schema suitable for both operational and analytical queries.

Key design features include:

- Primary keys for entity identification
- Foreign keys for relationships between entities
- Junction tables for many-to-many relationships
- Check constraints for controlled status values
- Timestamp fields for historical and time-based analysis
- Logical separation between operational entities and reporting-focused relationships

For example, maintenance work orders and users are connected through a separate assignment table. This allows one work order to have multiple assigned users and one user to participate in multiple work orders.

---

## 5. Data Generation and Population

The project uses Python-based data generation to populate the database with realistic synthetic data.

The generated data is designed to simulate a city infrastructure environment rather than simply fill tables with random values. The data generation logic considers:

- Different infrastructure zones
- Multiple asset types
- Asset statuses
- Sensor statuses
- Sensor readings over time
- Incident severity and status
- Maintenance work order creation
- Emergency dispatch records
- Transit disruption records
- Realistic relationships between entities

Large-volume tables, especially `sensor_readings`, are populated with many records to make reporting and performance testing meaningful.

Reference-style tables, such as roles or asset types, are smaller and more controlled. Operational tables, such as assets, sensors, readings, incidents, and work orders, contain larger generated datasets.

---

## 6. Operational Workflows Supported

The database supports several common operational workflows.

### Registering Users

Users can be stored with their role, contact details, and status. This supports responsibility tracking and assignment of work.

### Registering Infrastructure Assets

Assets are stored with their type, zone, location, installation date, and status. This allows the city to organize infrastructure geographically and functionally.

### Registering Sensors

Sensors are linked to assets and store information such as sensor type, unit of measurement, installation date, and status.

### Recording Sensor Readings

Sensor readings store measurements over time. This supports both real-time monitoring and historical analysis.

### Checking Threshold Violations

Sensor readings can be compared against threshold rules to identify warning or abnormal values.

### Creating Incidents

Incidents are created when abnormal conditions are detected or reported. They track the affected asset, related sensor, severity, description, status, and detection time.

### Creating Maintenance Work Orders

Maintenance work orders formalize repair or inspection tasks related to assets or incidents.

### Dispatching Emergency Units

Dispatch records track emergency unit response to serious incidents, including dispatch time, arrival time, and completion time.

### Recording Transit Impact

Transit impact records connect incidents to affected routes or vehicles and store information such as impact type, delay duration, and status.

---

## 7. Reporting and Analytical Queries

The project includes SQL reports designed to answer practical operational and analytical questions.

Examples of supported reports include:

- Zones with the highest number of incidents
- Asset types with the most incidents or maintenance work orders
- Assets with unusually high incident frequency
- Monthly or quarterly incident trends
- Open and closed maintenance work orders
- Average maintenance completion time
- Users or technicians with the highest number of assignments
- Sensors with frequent abnormal readings
- Assets that often cause threshold violations
- Emergency response time by incident, zone, or unit
- Transit routes most affected by infrastructure incidents

These reports demonstrate how SQL can be used not only for data retrieval, but also for performance monitoring, planning, and decision support.

---

## 8. SQL Concepts Demonstrated

The project demonstrates a wide range of SQL concepts.

### Joins

The reports use different join types depending on the business question:

- `INNER JOIN` for records that must have matching related data
- `LEFT JOIN` for complete reports that should include records even when related activity is missing
- `FULL OUTER JOIN` for comparison-style reports where matched and unmatched records on both sides matter

### Aggregation

Many reports use aggregate functions such as:

- `COUNT`
- `AVG`
- `MIN`
- `MAX`
- grouped summaries with `GROUP BY`
- filtered summaries with `HAVING`

### Subqueries

The project includes subqueries for cases such as:

- Finding incidents in the zone with the highest incident count
- Finding assets that have at least one related incident
- Comparing asset incident counts against zone-level averages
- Filtering records based on related table results

### Views

Views are used to simplify repeated reporting logic and make complex queries easier to reuse.

### Stored Functions and PL/pgSQL

The project includes PL/pgSQL functions for reusable database logic, such as status checks, calculated values, or repeated business rules.

### Triggers

Triggers are used to automate important database behavior, such as validating inserted data or reacting to changes in operational records.

### Indexes

Indexes are added to improve performance for frequently used query patterns, especially on large or frequently filtered tables.

---

## 9. Triggers, Functions, and Advanced Operations

The project includes advanced database operations to demonstrate how PostgreSQL can support business logic directly inside the database.

Examples of logic covered by advanced operations include:

- Checking inserted or updated data before accepting it
- Preventing invalid values
- Supporting status updates
- Supporting repeated calculations
- Improving query performance through indexes
- Testing performance impact with query plans

These features make the project more realistic because real operational databases often need more than basic table creation and simple SELECT queries.

---

## 10. Indexing and Performance Considerations

Because the system includes large operational tables, indexing is important for performance.

Important index candidates include:

- Sensor readings by sensor and reading time
- Incidents by status and detection time
- Incidents by asset
- Maintenance work orders by status and asset
- Dispatch records by incident and dispatch time

These indexes are useful because many reports filter by time period, status, asset, sensor, or incident. The goal is not to create indexes everywhere, but to create meaningful indexes that support actual query patterns.

Performance testing can be done with PostgreSQL tools such as:

```sql
EXPLAIN ANALYZE
```

This allows comparing query execution before and after index creation.

---

## 11. Repository Structure

The repository is organized into separate folders so that schema creation, data generation, reports, and documentation are easy to locate.

Typical structure:

```text
smart_city_infrastructure/
│
├── ERD/
│   └── database diagrams and entity-relationship materials
│
├── database_schema/
│   └── SQL DDL scripts for creating schemas, tables, constraints, and relationships
│
├── data_population/
│   └── Python and/or SQL scripts for generating and inserting sample data
│
├── reports/
│   └── analytical and operational SQL queries
│
├── advanced_operations/
│   └── indexes, triggers, functions, procedures, and performance-related SQL
│
├── documentation/
│   └── technical explanations and project overview files
│
└── README.md
```

The exact filenames may differ, but the project is structured so that each major database task has its own clear location.

---

## 12. How the Project Can Be Used

This project can be used to demonstrate:

- Relational database design
- PostgreSQL schema implementation
- Synthetic data generation with Python
- SQL reporting and analytics
- Data quality validation
- Advanced SQL features
- Database documentation
- GitHub-based project organization

It is especially relevant for roles involving data analysis, BI reporting, database systems, analytics engineering, or backend data workflows.

---

## 13. Main Learning Outcomes

Through this project, the team practiced:

- Designing a realistic relational database from a business domain
- Translating system requirements into entities and relationships
- Writing DDL scripts with constraints and foreign keys
- Generating realistic sample data programmatically
- Writing operational and analytical SQL queries
- Using joins, subqueries, aggregation, and views
- Implementing triggers and PL/pgSQL functions
- Thinking about indexing and query performance
- Documenting a technical database project clearly

---

## 14. Summary

The Smart City Infrastructure Management DBMS is a complete academic database project that models the operations of a smart city infrastructure monitoring system. It combines database design, realistic data generation, SQL reporting, and advanced PostgreSQL features.

The project shows how a database can support both daily operational tasks and higher-level analytical reporting, making it a strong example of practical database and data analysis work.
