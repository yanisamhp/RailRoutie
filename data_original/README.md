# Bambi Fare Data & Fare Engine Handoff v1

Project: Thai Public Transport Planner

## Objective

Develop verified fare datasets and a Python fare
calculation engine for integration with Dai's
routing engine and Streamlit prototype.

## Input Files

1. stations_coordinates_provisional.csv
   - 195 station-line records
   - Use station_line_id as the station key
   - Coordinates are provisional

2. lines_master.csv
   - 11 rail line records
   - Use line_id for line identification
   - Line metadata is provisional

3. ride_edges_master.csv
   - 184 ride edges
   - Useful for station sequence and route structure

4. interchanges_master.csv
   - 20 TRANSFER connections
   - 1 BRANCH_JUNCTION connection
   - Transfer conditions require verification

## Tasks

TASK 1: Fare Data Collection
- Collect official fare information for all 11 line IDs
- Record source URLs and effective dates
- Identify missing or unsupported fare coverage

TASK 2: Fare Dataset
- Build fare_rules.csv or fare_matrix.csv
- Match station IDs with the provided dataset
- Validate duplicate, missing and unmatched records

TASK 3: Fare Engine
- Develop fare_engine.py
- Accept a route from Dai's routing engine
- Calculate total fare using verified rules
- Handle transfers and operator boundaries
- Never invent missing fare values

TASK 4: Testing
- Compare calculated fares against official references
- Test same-line and cross-line journeys
- Report PASS, FAIL and REVIEW cases

TASK 5: Integration
- Agree on route input/output schema with Dai
- Support fare comparison across alternative routes
- Document limitations and unsupported journeys

## Required Deliverables

1. fare_rules.csv or fare_matrix.csv
2. fare_engine.py
3. fare_test_results.csv
4. fare_sources.csv
5. requirements.txt
6. README.md

## Important Notes

- Cheapest Route requires comparison of alternative
  routes, not just pricing one shortest route.
- Fare information must have traceable sources.
- Do not assume all transfers use the same fare rule.
- Missing fares must be reported as unavailable.
- Coordinate and line metadata remain provisional.

## Handoff Status

READY_FOR_BAMBI_FARE_DEVELOPMENT
