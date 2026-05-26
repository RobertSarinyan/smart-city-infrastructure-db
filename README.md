# Smart City Infrastructure Database Project

This project is a PostgreSQL-based database system for modeling and analyzing a smart city infrastructure management environment. It was created as part of a database **collaborative** course project and focuses on relational database design, synthetic data generation, advanced SQL reporting, and database operations.

The system models a city infrastructure network inspired by Yerevan-style districts and zones. It includes assets, sensors, sensor readings, incidents, work orders, maintenance activities, users, departments, contractors, and other operational entities.

## Disclaimer

This project uses fully synthetic data generated for academic and demonstration purposes.

Although the database is modeled around Yerevan-style districts, zones, infrastructure assets, sensors, incidents, and work orders, it does not represent real municipal, government, infrastructure, emergency-response, or sensor data.

The project is not affiliated with any official city authority or public agency.

## Project Goals

The main goal of this project is to demonstrate how a relational database can support smart city infrastructure monitoring and operations.

The project includes:

- A normalized PostgreSQL database schema
- Entity relationships and constraints
- Synthetic data generation using Python
- Realistic infrastructure-related sample data
- Advanced SQL reports
- Database functions, triggers, views, and indexes
- Documentation and ERD files

## Project Structure

```text
smart_city_infrastructure/
│
├── ERD/
│   └── smart_city_erd.png
│
├── database_schema/
│   └── ddl.sql
│
├── data_population/
│   ├── generate_data.py
│   └── write_sql.py
│
├── reports/
│   └── smart_city_real_life_reports.sql
│
├── advanced_operations/
│   └── smart_city_advanced_operations.sql
│
├── .gitignore
└── README.md
