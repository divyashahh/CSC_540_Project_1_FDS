# CSC 540 Project 1 — Freight Tracking and Delivery Management

## Project Overview

This project implements a freight tracking and delivery management system using:

- Python
- Tkinter GUI
- MariaDB 10.5
- `mysql-connector-python`

The application supports three user roles:

- **Shipper** — creates, updates, books, tracks, and reports on shipments
- **Carrier** — manages vehicles and departures, posts scan events, and views operational reports
- **Viewer** — read-only shipment tracking and performance reports

The application also includes the six required analytical queries.

---

## Setup Instructions

### 1. Clone the Repository

Open a terminal and run:

```bash
git clone https://github.com/divyashahh/CSC_540_Project_1_FDS.git
cd CSC_540_Project_1_FDS
```

If the repository has already been cloned, open the project folder in VS Code and run:

```bash
git pull
```

to make sure you have the latest version.

### 2. Connect to the NC State VPN

The MariaDB server is only accessible from the NC State network.

If you are off campus, connect to the **NC State VPN** before running the application.

Database server:

```text
classdb2.csc.ncsu.edu
```

Port:

```text
3306
```

DBeaver does **not** need to remain open while using the application. It is only needed if you want to manually inspect the database or load/reload the SQL files.

### 3. Install Python

Make sure Python 3 is installed.

Check with:

```bash
python --version
```

On some systems, the command may be:

```bash
python3 --version
```

### 4. Install the Required Python Package

From the project directory, run:

```bash
pip install mysql-connector-python
```

Tkinter is part of the standard Python installation on Windows and normally does not require a separate installation.

### 5. Create `config.py`

The repository contains:

```text
config_example.py
```

Create a copy of this file and name it:

```text
config.py
```

Do **not** commit `config.py` to GitHub because it contains your database password.

The file should look like:

```python
DB_CONFIG = {
    "host": "classdb2.csc.ncsu.edu",
    "port": 3306,
    "user": "your_unityid",
    "password": "your_mysql_password",
    "database": "your_database_name",
}
```

For the CSC database server, the username and database name will normally be your Unity ID.

Example:

```python
DB_CONFIG = {
    "host": "classdb2.csc.ncsu.edu",
    "port": 3306,
    "user": "your_unityid",
    "password": "your_mysql_password",
    "database": "your_unityid",
}
```

---

## Database Setup

The database only needs to be initialized before the first run, or whenever the schema/sample data need to be reset.

The SQL files are located in:

```text
sql/
```

The main files are:

```text
schema.sql
sample_data.sql
queries.sql
```

- `schema.sql` creates the tables, constraints, views, stored procedure, and triggers.
- `sample_data.sql` populates the database with the project sample data.
- `queries.sql` contains the six required analytical queries.

### Option A — DBeaver

1. Connect to the MariaDB server using:

```text
Host: classdb2.csc.ncsu.edu
Port: 3306
Database: your Unity ID/database
Username: your Unity ID
Password: your MariaDB password
```

2. Open a SQL editor connected to your database.

3. Open or paste the contents of:

```text
sql/schema.sql
```

4. Execute the entire script.

5. Then open or paste:

```text
sql/sample_data.sql
```

6. Execute the entire script.

7. Verify the setup with:

```sql
SHOW TABLES;
```

The project database should contain the freight-tracking tables such as:

```text
hub
user_account
carrier
shipper
viewer
vehicle
box_truck
refrigerated_van
rail_car
departure
shipment
booking
scan_event
```

It also contains the supporting departure-load view.

DBeaver can be closed after this setup is complete.

### Option B — MariaDB / MySQL Shell

The SQL files can also be loaded directly through the NC State database shell.

Connect to the MariaDB server with your Unity credentials, select your database, and execute:

```sql
SOURCE path/to/sql/schema.sql;
SOURCE path/to/sql/sample_data.sql;
```

Then verify with:

```sql
SHOW TABLES;
```

---

## Test the Database Connection

Before launching the GUI, you can verify the connection by running:

```bash
python test_conn.py
```

A successful connection should show the MariaDB server version and confirm that the project tables contain the expected sample data.

If the connection fails, check:

- NC State VPN is connected if off campus
- `config.py` exists
- database username is correct
- database password is correct
- database name is correct
- `mysql-connector-python` is installed

---

## Run the Application

From the root project directory, run:

```bash
python gui.py
```

The **Freight Tracking and Delivery Management** window should open.

The GUI checks the database connection when it starts, so the VPN/database connection must already be available.

DBeaver does **not** need to be open.

---

## Demo Login Accounts

All demo accounts use the password:

```text
password123
```

### Shipper Accounts

```text
triangle
oakcity
carolina
coastal
```

Example:

```text
Username: triangle
Password: password123
```

### Carrier Accounts

```text
piedmont
atlantic
plains
```

Example:

```text
Username: piedmont
Password: password123
```

### Viewer Account

```text
fedex
```

Example:

```text
Username: fedex
Password: password123
```

---

## Application Features

### Shipper

The Shipper interface allows users to:

- Create shipments
- Update unbooked shipments
- Book shipments onto departures
- Track shipment movement history
- View on-time vs. late delivery reports
- View in-transit shipments
- View shipments approaching their promised delivery date

Shippers are restricted to their own shipments.

### Carrier

The Carrier interface allows users to:

- Add vehicles
- Update vehicle information
- View vehicles
- Schedule departures
- Update departures
- View departures
- Post shipment scan events
- View departure load/utilization reports
- View carrier on-time delivery reports
- View shipment dwell-time reports

Carriers can only manage vehicles and departures belonging to their own carrier account and can only scan shipments assigned to departures they operate.

### Viewer

The Viewer interface is read-only and includes:

- Shipment tracking
- On-time rates by lane
- On-time rates by carrier
- Lane volume ranking
- Top departures per lane
- Shipment dwell-time reports
- Running delivery totals by carrier
- At-risk in-transit shipments

### Required Analytical Queries

The application includes the six required analytical queries:

1. Number of vehicles of each type per carrier
2. Departures ranked by weight utilization per lane
3. Dwell time between consecutive scans for a shipment
4. Running total of delivered weight by week per carrier
5. Departures carrying shipments from at least two different shippers
6. Shipments with no scan events

---

## Project Structure

```text
CSC_540_Project_1_FDS/
│
├── README.md
├── gui.py
├── main.py
├── test_conn.py
├── config_example.py
├── config.py                  # local only; do NOT commit
│
├── app/
│   ├── auth.py
│   ├── carrier.py
│   ├── common.py
│   ├── db.py
│   ├── shipper.py
│   ├── viewer.py
│   └── view_queries.py
│
├── docs/
│   ├── er_diagram_final.png    # final diagram
│   ├── er_diagram_old.png
│   ├── old_report.pdf
│   └── update_para.txt         # differences between er diagram paragraph
│
└── sql/
    ├── schema.sql
    ├── sample_data.sql
    ├── queries.sql
    └── test_queries.sql
```
## Docs

- `er_diagram_final.png` – Final ER diagram reflecting improvements to the original database design.
- `er_diagram_old.png` – Original ER diagram, included for comparison.
- `old_report.pdf` – Previous project report.
- `update_para.txt` – Brief explanation of the improvements and changes made between the original and final ER diagrams.
  
---

## Important Notes

- Connect to the NC State VPN when off campus.
- DBeaver is optional after the database has been initialized.
- Always run the application from the project root directory.
- Do not commit `config.py`.
- The application connects directly to MariaDB through Python using `mysql-connector-python`.
- If the database has been reset, rerun `schema.sql` and then `sample_data.sql` before starting the application.

### Team Members

- Divya Shah — dbshah5
- Lasya Banka — lbanka
- Madhu Gopinath — mgopina
- Nimra Shaik — nshaik2
