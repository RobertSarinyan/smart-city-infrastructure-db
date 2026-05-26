SET search_path TO smart_city, public;


-- Report 1: Overall Operational Dashboard Summary
-- Purpose: Gives managers a quick high-level overview of the current database state.

SELECT
    (SELECT COUNT(*) FROM assets) AS total_assets,
    (SELECT COUNT(*) FROM sensors) AS total_sensors,
    (SELECT COUNT(*) FROM sensor_readings) AS total_sensor_readings,
    (SELECT COUNT(*) FROM incidents) AS total_incidents,
    (SELECT COUNT(*) FROM maintenance_work_orders) AS total_work_orders,
    (SELECT COUNT(*) FROM dispatch_records) AS total_dispatches,
    (SELECT COUNT(*) FROM incident_transit_impacts) AS total_transit_impacts;


-- Report 2: High-Risk Zones by Incident Count
-- Purpose: Shows which city zones have the highest number of incidents.

SELECT
    z.district_name,
    z.zone_name,
    COUNT(i.incident_id) AS total_incidents
FROM zones z
JOIN assets a
    ON a.zone_id = z.zone_id
JOIN incidents i
    ON i.asset_id = a.asset_id
GROUP BY
    z.district_name,
    z.zone_name
ORDER BY
    total_incidents DESC;


-- Report 3: Incident Severity by Zone
-- Purpose: Shows how many incidents of each severity level happened in each zone.

SELECT
    z.district_name,
    z.zone_name,
    i.severity,
    COUNT(i.incident_id) AS total_incidents
FROM zones z
JOIN assets a
    ON a.zone_id = z.zone_id
JOIN incidents i
    ON i.asset_id = a.asset_id
GROUP BY
    z.district_name,
    z.zone_name,
    i.severity
ORDER BY
    z.district_name,
    z.zone_name,
    total_incidents DESC;


-- Report 4: Asset Types with the Most Incidents
-- Purpose: Shows which infrastructure asset categories fail most often.

SELECT
    at.type_name AS asset_type,
    COUNT(DISTINCT a.asset_id) AS total_assets_of_type,
    COUNT(DISTINCT i.incident_id) AS incident_count
FROM asset_types at
JOIN assets a
    ON a.asset_type_id = at.asset_type_id
LEFT JOIN incidents i
    ON i.asset_id = a.asset_id
GROUP BY
    at.type_name
ORDER BY
    incident_count DESC;


-- Report 5: Asset Types with the Most Maintenance Work Orders
-- Purpose: Shows which asset categories require the most maintenance work.

SELECT
    at.type_name AS asset_type,
    COUNT(DISTINCT mwo.work_order_id) AS work_order_count
FROM asset_types at
JOIN assets a
    ON a.asset_type_id = at.asset_type_id
LEFT JOIN maintenance_work_orders mwo
    ON mwo.asset_id = a.asset_id
GROUP BY
    at.type_name
ORDER BY
    work_order_count DESC;


-- Report 6: Current Open Incident Queue
-- Purpose: Lists incidents that are still not resolved or closed.

SELECT
    i.incident_id,
    i.incident_type,
    i.severity,
    i.status,
    i.detected_at,
    a.asset_name,
    at.type_name AS asset_type,
    z.district_name,
    z.zone_name
FROM incidents i
JOIN assets a
    ON a.asset_id = i.asset_id
JOIN asset_types at
    ON at.asset_type_id = a.asset_type_id
JOIN zones z
    ON z.zone_id = a.zone_id
WHERE i.status = 'detected'
   OR i.status = 'in_progress'
ORDER BY
    i.detected_at;


-- Report 7: Maintenance Work Orders by Priority and Status
-- Purpose: Gives a simple overview of maintenance workload.

SELECT
    priority,
    status,
    COUNT(work_order_id) AS total_work_orders
FROM maintenance_work_orders
GROUP BY
    priority,
    status
ORDER BY
    priority,
    status;


-- Report 8: Maintenance Workload by User
-- Purpose: Shows which users have the most work order assignments.

SELECT
    u.user_id,
    u.first_name,
    u.last_name,
    r.role_name,
    COUNT(woa.assignment_id) AS total_assignments
FROM users u
JOIN roles r
    ON r.role_id = u.role_id
JOIN work_order_assignments woa
    ON woa.user_id = u.user_id
GROUP BY
    u.user_id,
    u.first_name,
    u.last_name,
    r.role_name
ORDER BY
    total_assignments DESC;


-- Report 9: Work Order Completion Time by Priority
-- Purpose: Shows how long completed or closed work orders take by priority.

SELECT
    priority,
    COUNT(work_order_id) AS completed_work_orders,
    AVG(closed_at - opened_at) AS average_completion_time,
    MAX(closed_at - opened_at) AS maximum_completion_time
FROM maintenance_work_orders
WHERE closed_at IS NOT NULL
GROUP BY
    priority
ORDER BY
    priority;


-- Report 10: Emergency Dispatches by Unit
-- Purpose: Shows which emergency units were dispatched most often.

SELECT
    eu.unit_name,
    eu.unit_type,
    eu.base_location,
    COUNT(dr.dispatch_id) AS total_dispatches
FROM emergency_units eu
LEFT JOIN dispatch_records dr
    ON dr.emergency_unit_id = eu.emergency_unit_id
GROUP BY
    eu.unit_name,
    eu.unit_type,
    eu.base_location
ORDER BY
    total_dispatches DESC;


-- Report 11: Emergency Dispatches by Zone
-- Purpose: Shows which city zones required the most emergency dispatch activity.

SELECT
    z.district_name,
    z.zone_name,
    COUNT(dr.dispatch_id) AS total_dispatches
FROM dispatch_records dr
JOIN incidents i
    ON i.incident_id = dr.incident_id
JOIN assets a
    ON a.asset_id = i.asset_id
JOIN zones z
    ON z.zone_id = a.zone_id
GROUP BY
    z.district_name,
    z.zone_name
ORDER BY
    total_dispatches DESC;


-- Report 12: Emergency Response Time by Unit
-- Purpose: Shows average arrival time after dispatch for each emergency unit.

SELECT
    eu.unit_name,
    eu.unit_type,
    COUNT(dr.dispatch_id) AS total_dispatches,
    AVG(dr.arrival_time - dr.dispatch_time) AS average_response_time
FROM emergency_units eu
JOIN dispatch_records dr
    ON dr.emergency_unit_id = eu.emergency_unit_id
WHERE dr.arrival_time IS NOT NULL
GROUP BY
    eu.unit_name,
    eu.unit_type
ORDER BY
    average_response_time DESC;

-- Report 13: Sensors with Abnormal Readings
-- Purpose: Shows sensors that produced warning, critical, or invalid readings.

SELECT
    s.sensor_id,
    s.sensor_type,
    s.status AS sensor_status,
    sr.quality_flag,
    a.asset_name,
    at.type_name AS asset_type,
    z.district_name,
    z.zone_name,
    COUNT(sr.reading_id) AS abnormal_readings
FROM sensors s
JOIN assets a
    ON a.asset_id = s.asset_id
JOIN asset_types at
    ON at.asset_type_id = a.asset_type_id
JOIN zones z
    ON z.zone_id = a.zone_id
JOIN sensor_readings sr
    ON sr.sensor_id = s.sensor_id
WHERE sr.quality_flag = 'warning'
   OR sr.quality_flag = 'critical'
   OR sr.quality_flag = 'invalid'
GROUP BY
    s.sensor_id,
    s.sensor_type,
    s.status,
    sr.quality_flag,
    a.asset_name,
    at.type_name,
    z.district_name,
    z.zone_name
ORDER BY
    abnormal_readings DESC;


-- Report 14: Sensor Reading Quality Summary
-- Purpose: Gives a general summary of normal, warning, critical, and invalid readings.

SELECT
    quality_flag,
    COUNT(reading_id) AS total_readings
FROM sensor_readings
GROUP BY
    quality_flag
ORDER BY
    total_readings DESC;


-- Report 15: Transit Disruption Impact Report
-- Purpose: Shows which incidents caused delays in public transportation.

SELECT
    tr.route_code,
    tr.route_name,
    tv.vehicle_number,
    tv.vehicle_type,
    i.incident_type,
    i.severity,
    iti.impact_type,
    iti.delay_minutes,
    iti.status AS impact_status,
    iti.recorded_at
FROM incident_transit_impacts iti
JOIN incidents i
    ON i.incident_id = iti.incident_id
JOIN transit_routes tr
    ON tr.route_id = iti.route_id
JOIN transit_vehicles tv
    ON tv.vehicle_id = iti.vehicle_id
ORDER BY
    iti.delay_minutes DESC;


-- Report 16: Route-Level Transit Delay Summary
-- Purpose: Summarizes total and average delay for each transit route.

SELECT
    tr.route_code,
    tr.route_name,
    COUNT(iti.impact_id) AS total_impact_records,
    SUM(iti.delay_minutes) AS total_delay_minutes,
    AVG(iti.delay_minutes) AS average_delay_minutes,
    MAX(iti.delay_minutes) AS maximum_delay_minutes
FROM transit_routes tr
LEFT JOIN incident_transit_impacts iti
    ON iti.route_id = tr.route_id
GROUP BY
    tr.route_code,
    tr.route_name
ORDER BY
    total_delay_minutes DESC NULLS LAST;


-- Report 17: Asset Status Distribution by Zone
-- Purpose: Shows how many assets of each status exist in each zone.

SELECT
    z.district_name,
    z.zone_name,
    a.status,
    COUNT(a.asset_id) AS total_assets
FROM zones z
LEFT JOIN assets a
    ON a.zone_id = z.zone_id
GROUP BY
    z.district_name,
    z.zone_name,
    a.status
ORDER BY
    z.district_name,
    z.zone_name,
    total_assets DESC;


-- Report 18: Incidents by Type
-- Purpose: Shows the most common incident types in the system.

SELECT
    incident_type,
    COUNT(incident_id) AS total_incidents
FROM incidents
GROUP BY
    incident_type
ORDER BY
    total_incidents DESC;


-- Report 19: Incident and Transit Impact Comparison
-- Purpose: Compares incidents and transit impact records, including matched and unmatched cases.

SELECT
    i.incident_id,
    i.incident_type,
    i.severity,
    i.status AS incident_status,
    iti.impact_id,
    iti.impact_type,
    iti.delay_minutes,
    iti.status AS impact_status
FROM incidents i
FULL OUTER JOIN incident_transit_impacts iti
    ON iti.incident_id = i.incident_id
ORDER BY
    i.incident_id,
    iti.impact_id;


-- Report 20: Incidents in the Zone with the Highest Incident Count
-- Purpose: Finds incidents that happened in the zone with the largest number of incidents.

SELECT
    i.incident_id,
    i.incident_type,
    i.severity,
    i.status,
    a.asset_name,
    z.district_name,
    z.zone_name
FROM incidents i
JOIN assets a
    ON a.asset_id = i.asset_id
JOIN zones z
    ON z.zone_id = a.zone_id
WHERE z.zone_id = (
    SELECT z2.zone_id
    FROM zones z2
    JOIN assets a2
        ON a2.zone_id = z2.zone_id
    JOIN incidents i2
        ON i2.asset_id = a2.asset_id
    GROUP BY
        z2.zone_id
    ORDER BY
        COUNT(i2.incident_id) DESC
    LIMIT 1
)
ORDER BY
    i.detected_at;


-- Report 21: Assets That Have at Least One Incident
-- Purpose: Lists assets that were involved in at least one incident.

SELECT
    a.asset_id,
    a.asset_name,
    at.type_name AS asset_type,
    z.district_name,
    z.zone_name,
    a.status
FROM assets a
JOIN asset_types at
    ON at.asset_type_id = a.asset_type_id
JOIN zones z
    ON z.zone_id = a.zone_id
WHERE EXISTS (
    SELECT 1
    FROM incidents i
    WHERE i.asset_id = a.asset_id
)
ORDER BY
    z.district_name,
    z.zone_name,
    a.asset_name;


-- Report 22: Users Assigned to Maintenance Work Orders
-- Purpose: Lists users who have been assigned to at least one work order.

SELECT
    u.user_id,
    u.first_name,
    u.last_name,
    r.role_name,
    u.status
FROM users u
JOIN roles r
    ON r.role_id = u.role_id
WHERE u.user_id IN (
    SELECT woa.user_id
    FROM work_order_assignments woa
)
ORDER BY
    r.role_name,
    u.last_name,
    u.first_name;


-- Report 23: Assets with More Incidents Than the Average in Their Zone
-- Purpose: Finds locally high-risk assets by comparing each asset with assets in the same zone.

SELECT
    a.asset_id,
    a.asset_name,
    at.type_name AS asset_type,
    z.district_name,
    z.zone_name,
    (
        SELECT COUNT(*)
        FROM incidents i
        WHERE i.asset_id = a.asset_id
    ) AS asset_incident_count
FROM assets a
JOIN asset_types at
    ON at.asset_type_id = a.asset_type_id
JOIN zones z
    ON z.zone_id = a.zone_id
WHERE (
    SELECT COUNT(*)
    FROM incidents i
    WHERE i.asset_id = a.asset_id
) >
(
    SELECT AVG(asset_counts.incident_count)
    FROM (
        SELECT
            a2.asset_id,
            COUNT(i2.incident_id) AS incident_count
        FROM assets a2
        LEFT JOIN incidents i2
            ON i2.asset_id = a2.asset_id
        WHERE a2.zone_id = a.zone_id
        GROUP BY
            a2.asset_id
    ) asset_counts
)
ORDER BY
    asset_incident_count DESC;


-- Report 24: Combined Active Operational Queue
-- Purpose: Combines active incidents and active work orders into one operational queue.

SELECT
    'Incident' AS record_type,
    i.incident_id AS record_id,
    i.severity AS priority_level,
    i.status AS current_status,
    i.detected_at AS created_time,
    a.asset_name
FROM incidents i
JOIN assets a
    ON a.asset_id = i.asset_id
WHERE i.status = 'detected'
   OR i.status = 'in_progress'

UNION ALL

SELECT
    'Work Order' AS record_type,
    mwo.work_order_id AS record_id,
    mwo.priority AS priority_level,
    mwo.status AS current_status,
    mwo.opened_at AS created_time,
    a.asset_name
FROM maintenance_work_orders mwo
JOIN assets a
    ON a.asset_id = mwo.asset_id
WHERE mwo.status = 'open'
   OR mwo.status = 'assigned'
   OR mwo.status = 'in_progress'

ORDER BY
    created_time;


-- Report 25: Assets with No Incidents
-- Purpose: Shows assets that have not been involved in incidents.

SELECT
    a.asset_id,
    a.asset_name,
    at.type_name AS asset_type,
    z.district_name,
    z.zone_name,
    a.status
FROM assets a
JOIN asset_types at
    ON at.asset_type_id = a.asset_type_id
JOIN zones z
    ON z.zone_id = a.zone_id
LEFT JOIN incidents i
    ON i.asset_id = a.asset_id
WHERE i.incident_id IS NULL
ORDER BY
    z.district_name,
    z.zone_name,
    a.asset_name;


-- Report 26: Users Without Work Order Assignments
-- Purpose: Shows users who exist in the system but have no maintenance assignments.

SELECT
    u.user_id,
    u.first_name,
    u.last_name,
    r.role_name,
    u.status
FROM users u
JOIN roles r
    ON r.role_id = u.role_id
LEFT JOIN work_order_assignments woa
    ON woa.user_id = u.user_id
WHERE woa.assignment_id IS NULL
ORDER BY
    r.role_name,
    u.last_name,
    u.first_name;