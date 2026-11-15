import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app import db

root = None
me = {"id": None, "name": None}      # the logged-in account (access control is applied against this)

STATUS_CHOICES = {
    "Received": "RECEIVED", "In Transit": "IN_TRANSIT", "Arrived at Hub": "ARRIVED_AT_HUB",
    "Out for Delivery": "OUT_FOR_DELIVERY", "Delivered": "DELIVERED",
}
VEHICLE_TYPES = {"Box Truck": "BOX_TRUCK", "Refrigerated Van": "REFRIGERATED_VAN", "Rail Car": "RAIL_CAR"}
# vehicle type -> (subtype table, [(column, label, input kind)])
TYPE_DETAILS = {
    "BOX_TRUCK": ("box_truck", [("cargo_volume_m3", "Cargo Volume (m3)", "dec"),
                                ("gross_weight_rating_kg", "Gross Weight Rating (kg)", "dec")]),
    "REFRIGERATED_VAN": ("refrigerated_van", [("min_temperature_c", "Minimum Temperature (C)", "dec_any"),
                                              ("max_temperature_c", "Maximum Temperature (C)", "dec_any"),
                                              ("payload_limit_kg", "Payload Limit (kg)", "dec")]),
    "RAIL_CAR": ("rail_car", [("axle_count", "Axle Count", "id"),
                              ("track_gauge_mm", "Track Gauge (mm)", "dec")]),
}


class Rejected(Exception):
    """A business-rule failure (ownership, state, ...) that should be shown to the user."""


# =========================================================
# GENERAL HELPERS
# =========================================================

def err_text(e):
    return getattr(e, "msg", None) or str(e)


def clear_root():
    for widget in root.winfo_children():
        widget.destroy()


def create_title(text, subtitle=None):
    ttk.Label(root, text=text, font=("Arial", 18, "bold")).pack(pady=(20, 6))
    if subtitle:
        ttk.Label(root, text=subtitle, font=("Arial", 11)).pack(pady=(0, 10))


def fmt(value):
    return "-" if value is None else value


def create_tree(parent, columns, headings, widths=None, height=8):
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
    for i, column in enumerate(columns):
        tree.heading(column, text=headings[i])
        tree.column(column, width=widths[i] if widths else 120, anchor="center")
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return tree


def fill_tree(tree, rows):
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", "end", values=[fmt(v) for v in row])


def table(columns, headings, widths, rows=(), height=None):
    """Result tables (no height given) stretch to fill the window; reference tables keep a fixed
    number of rows so the buttons below them always stay visible."""
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=height is None, padx=20, pady=6)
    tree = create_tree(frame, columns, headings, widths, height or 8)
    fill_tree(tree, rows)
    return tree


def note(text, bold=False):
    ttk.Label(root, text=text, font=("Arial", 10, "bold" if bold else "normal")).pack(pady=(8, 0))


def action_bar(buttons):
    """Numbered buttons exactly like the flow document: '1. Save', '2. Cancel', ..."""
    for i, (label, command) in enumerate(buttons, 1):
        ttk.Button(root, text=f"{i}. {label}", command=command, width=30).pack(pady=3)


def menu_page(heading, subtitle, items):
    clear_root()
    create_title(heading, subtitle)
    action_bar(items)


def get_hubs():
    _, rows = db.query("SELECT hub_id FROM hub ORDER BY hub_id")
    return [r[0] for r in rows]


def run_action(action, ok_title, error_title, back):
    """Run the database operation and navigate only if it succeeds."""
    try:
        result = action()
        messagebox.showinfo(ok_title, result)
    except Rejected as e:
        messagebox.showerror("Not Allowed", str(e))
        return
    except Exception as e:
        messagebox.showerror(error_title, err_text(e))
        return

    # Only navigate away after a successful operation.
    back()

# ---------- input validation (every parser raises ValueError with a readable message) ----------

def parse_int(text, label, minimum=1):
    try:
        n = int(text)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.")
    if n < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    return n


def parse_decimal(text, label, positive=True):
    try:
        n = Decimal(text)
        if not n.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        raise ValueError(f"{label} must be a number.")
    if positive and n <= 0:
        raise ValueError(f"{label} must be greater than 0.")
    return n


def parse_date(text, label):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{label} must use the format YYYY-MM-DD.")


def parse_datetime(text, label):
    for fmt_ in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt_)
        except ValueError:
            pass
    raise ValueError(f"{label} must use the format YYYY-MM-DD HH:MM.")


def parse_hub(text, label):
    hubs = get_hubs()
    code = text.upper()
    if code not in hubs:
        raise ValueError(f"{label} '{text}' is not a valid hub. Valid hubs: {', '.join(hubs)}")
    return code


PARSERS = {
    "text": lambda t, l: t,
    "password": lambda t, l: t,
    "choice": lambda t, l: t,
    "id": lambda t, l: parse_int(t, l, 1),
    "n": lambda t, l: parse_int(t, l, 0),
    "dec": lambda t, l: parse_decimal(t, l, True),
    "dec_any": lambda t, l: parse_decimal(t, l, False),
    "date": parse_date,
    "datetime": parse_datetime,
    "hub": parse_hub,
}


def build_form(specs):
    """specs: (key, label, kind[, default[, options]]). Returns {key: (widget, kind, label)}.
    Kinds ending in _opt are optional (blank -> None)."""
    frame = ttk.Frame(root)
    frame.pack(pady=8)
    widgets = {}
    for i, spec in enumerate(specs):
        key, label, kind = spec[0], spec[1], spec[2]
        default = spec[3] if len(spec) > 3 else ""
        options = spec[4] if len(spec) > 4 else None
        ttk.Label(frame, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
        if kind.startswith("choice"):
            widget = ttk.Combobox(frame, values=options, state="readonly", width=28)
            if default:
                widget.set(default)
        else:
            widget = ttk.Entry(frame, width=31, show="*" if kind == "password" else "")
            if default != "":
                widget.insert(0, str(default))
        widget.grid(row=i, column=1, padx=10, pady=5)
        widgets[key] = (widget, kind, label)
    return widgets


def read_form(widgets):
    """Validate every field; raises ValueError (message names the field) so the page can re-prompt."""
    values = {}
    for key, (widget, kind, label) in widgets.items():
        text = widget.get() if kind == "password" else widget.get().strip()
        optional = kind.endswith("_opt")
        base = kind[:-4] if optional else kind
        if text == "":
            if optional:
                values[key] = None
                continue
            raise ValueError(f"{label} is required.")
        values[key] = PARSERS[base](text, label)
    return values


def set_entry(widget, value):
    if isinstance(widget, ttk.Combobox):
        widget.set(str(value))
    else:
        widget.delete(0, tk.END)
        widget.insert(0, str(value))


def date_range(v):
    start, end = v["start"], v["end"]
    if start > end:
        raise ValueError("Start Date must not be after End Date.")
    return start, end


DATE_SPECS = [("start", "Start Date (YYYY-MM-DD)", "date", "2026-01-01"),
              ("end", "End Date (YYYY-MM-DD)", "date", date.today().isoformat())]


def report_page(heading, specs, run, columns, headings, widths, back, landing,
                run_label="View Report", back_label="GoBack", landing_label="LandingPage"):
    """Form -> run(values) -> (rows, summary text) shown below. With no form fields the report
    is shown immediately and only the navigation buttons remain (as in the flow document)."""
    clear_root()
    create_title(heading)
    widgets = build_form(specs) if specs else {}
    summary = ttk.Label(root, text="", font=("Arial", 11, "bold"))
    summary.pack(pady=4)
    tree = table(columns, headings, widths)

    def view():
        try:
            values = read_form(widgets) if widgets else {}
            rows, text = run(values)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return
        except Rejected as e:
            messagebox.showerror("Not Allowed", str(e))
            return
        except Exception as e:
            messagebox.showerror("Report Error", err_text(e))
            return
        fill_tree(tree, rows)
        summary.config(text=text if rows or text else "")
        if not rows and not text:
            summary.config(text="No matching rows.")

    buttons = [(run_label, view)] if widgets else []
    action_bar(buttons + [(back_label, back), (landing_label, landing)])
    if not widgets:
        view()


def tracking_page(heading, owner_only, back, landing):
    """Shared by Shipper: Track Shipment (own shipments only) and Viewer: Track Shipment (read-only)."""
    clear_root()
    create_title(heading)
    widgets = build_form([("sid", "Shipment ID", "id")])
    info = ttk.Label(root, text="", justify="left", font=("Arial", 11))
    info.pack(pady=8)
    tree = table(("seq", "time", "hub", "status"), ("Seq", "Timestamp", "Hub", "Status"), (60, 190, 80, 170))

    def view():
        try:
            v = read_form(widgets)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return
        sql = ("SELECT s.shipment_id, sh.shipper_name, s.origin_hub_id, s.destination_hub_id, s.weight_kg, "
               "s.promised_delivery_date, COALESCE(s.current_status, 'NO SCANS YET'), "
               "COALESCE(s.delivery_outcome, '-') FROM shipment s "
               "JOIN shipper sh ON sh.account_id = s.shipper_id WHERE s.shipment_id = %s")
        params = [v["sid"]]
        if owner_only:
            sql += " AND s.shipper_id = %s"
            params.append(me["id"])
        try:
            _, rows = db.query(sql, params)
            if not rows:
                info.config(text="")
                fill_tree(tree, [])
                messagebox.showerror("Not Found", "That shipment does not exist"
                                     + (" or is not owned by you." if owner_only else "."))
                return
            r = rows[0]
            info.config(text=(f"Shipment {r[0]}   Shipper: {r[1]}\nRoute: {r[2]} -> {r[3]}   Weight: {r[4]} kg\n"
                              f"Promised: {r[5]}\nCurrent Status: {r[6]}   Delivery Outcome: {r[7]}"))
            _, scans = db.query("SELECT scan_sequence_no, scan_timestamp, hub_id, status FROM scan_event "
                                "WHERE shipment_id = %s ORDER BY scan_sequence_no", (v["sid"],))
            fill_tree(tree, scans)
        except Exception as e:
            messagebox.showerror("Tracking Error", err_text(e))

    action_bar([("View History", view), ("GoBack", back), ("LandingPage", landing)])


DWELL_SQL = """
SELECT shipment_id, scan_sequence_no, status, hub_id, scan_timestamp,
       LAG(scan_timestamp) OVER w AS previous_scan_time,
       LAG(hub_id) OVER w AS previous_hub,
       TIMESTAMPDIFF(MINUTE, LAG(scan_timestamp) OVER w, scan_timestamp) AS minutes_since_previous,
       ROUND(TIMESTAMPDIFF(MINUTE, LAG(scan_timestamp) OVER w, scan_timestamp) / 60, 2) AS hours_since_previous
FROM scan_event
WHERE shipment_id = %s
WINDOW w AS (PARTITION BY shipment_id ORDER BY scan_sequence_no)
ORDER BY scan_sequence_no
"""
DWELL_COLS = (("shipment", "seq", "status", "hub", "time", "prevtime", "prevhub", "minutes", "hours"),
              ("Shipment", "Seq", "Status", "Hub", "Timestamp", "Previous Time", "Previous Hub", "Minutes", "Hours"),
              (80, 50, 140, 60, 150, 150, 100, 80, 70))


# =========================================================
# HOME + LOGIN
# =========================================================

def show_home():
    me.update(id=None, name=None)
    menu_page("Freight Tracking and Delivery Management", "Select an option", [
        ("Shipper Login", lambda: show_login("Shipper")),
        ("Carrier Login", lambda: show_login("Carrier")),
        ("Viewer Login", lambda: show_login("Viewer")),
        ("Exit", root.destroy),
    ])


def show_login(role):
    clear_root()
    create_title(f"{role} Login")
    widgets = build_form([("user", "User ID", "text"), ("pw", "Password", "password")])
    landing = {"Shipper": shipper_landing, "Carrier": carrier_landing, "Viewer": viewer_landing}[role]

    def sign_in():
        user = widgets["user"][0].get().strip()
        password = widgets["pw"][0].get()
        if not user or not password:
            messagebox.showwarning("Missing Information", "Enter both User ID and Password.")
            return
        try:
            _, rows = db.query(
                "SELECT a.account_id, COALESCE(c.carrier_name, s.shipper_name, a.username) "
                "FROM user_account a LEFT JOIN carrier c ON c.account_id = a.account_id "
                "LEFT JOIN shipper s ON s.account_id = a.account_id "
                "WHERE a.username = %s AND a.password_hash = SHA2(%s, 256) AND a.role = %s",
                (user, password, role))
        except Exception as e:
            messagebox.showerror("Database Error", err_text(e))
            return
        if not rows:
            messagebox.showerror("Login Incorrect", "Login Incorrect. Please enter your credentials again.")
            widgets["pw"][0].delete(0, tk.END)
            return
        me.update(id=rows[0][0], name=rows[0][1])
        landing()

    widgets["pw"][0].bind("<Return>", lambda e: sign_in())
    action_bar([("Sign-In", sign_in), ("GoBack", show_home)])


# =========================================================
# SHIPPER
# =========================================================

MY_SHIPMENTS_SQL = (
    "SELECT s.shipment_id, s.origin_hub_id, s.destination_hub_id, s.weight_kg, s.promised_delivery_date, "
    "COALESCE(s.current_status, 'NO SCANS YET'), b.departure_id "
    "FROM shipment s LEFT JOIN booking b ON b.shipment_id = s.shipment_id "
    "WHERE s.shipper_id = %s ORDER BY s.shipment_id")
MY_SHIPMENTS_COLS = (("id", "origin", "dest", "weight", "promised", "status", "dep"),
                     ("Shipment", "Origin", "Destination", "Weight kg", "Promised", "Status", "Departure"),
                     (80, 80, 100, 90, 110, 140, 90))


def shipper_landing():
    menu_page(f"Welcome, {me['name']}", "Shipper: Landing", [
        ("Manage Shipments", shipper_manage),
        ("Reports", shipper_reports_menu),
        ("Logout", show_home),
    ])


def shipper_manage():
    menu_page("Manage Shipments", "Shipper: Manage Shipments", [
        ("Create Shipment", shipper_create),
        ("Update Shipment", shipper_update),
        ("Book Shipment onto Departure", shipper_book),
        ("Track Shipment", shipper_track),
        ("GoBack", shipper_landing),
        ("LandingPage", shipper_landing),
    ])


def shipper_create():
    clear_root()
    create_title("Create Shipment")
    w = build_form([("origin", "Origin Hub ID", "hub"), ("dest", "Destination Hub ID", "hub"),
                    ("weight", "Weight (kg)", "dec"), ("promised", "Promised Delivery Date (YYYY-MM-DD)", "date")])
    note("Hubs: " + ", ".join(get_hubs()))

    def save():
        try:
            v = read_form(w)
            if v["origin"] == v["dest"]:
                raise ValueError("Origin and destination hubs must be different.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            new_id = db.execute(
                "INSERT INTO shipment (shipper_id, origin_hub_id, destination_hub_id, weight_kg, "
                "promised_delivery_date) VALUES (%s, %s, %s, %s, %s)",
                (me["id"], v["origin"], v["dest"], v["weight"], v["promised"]))
            return (f"Shipment {new_id} was created: {v['origin']} -> {v['dest']}, "
                    f"{v['weight']} kg, promised {v['promised']}.")
        run_action(action, "Shipment Created", "Create Shipment Failed", shipper_manage)

    action_bar([("Save", save), ("Cancel", shipper_manage), ("LandingPage", shipper_landing)])


def shipper_update():
    clear_root()
    create_title("Update Shipment")
    w = build_form([("sid", "Shipment ID", "id"), ("origin", "Origin Hub ID", "hub"),
                    ("dest", "Destination Hub ID", "hub"), ("weight", "Weight (kg)", "dec"),
                    ("promised", "Promised Delivery Date (YYYY-MM-DD)", "date")])
    note("Enter a Shipment ID and press Tab to load its current values. Only unbooked shipments can be changed.")
    cols = MY_SHIPMENTS_COLS
    table(cols[0], cols[1], cols[2], db.query(MY_SHIPMENTS_SQL, (me["id"],))[1], height=6)

    def prefill(event=None):
        try:
            text = w["sid"][0].get().strip()
            if not text.isdigit():
                return
            _, rows = db.query("SELECT origin_hub_id, destination_hub_id, weight_kg, promised_delivery_date "
                               "FROM shipment WHERE shipment_id = %s AND shipper_id = %s", (int(text), me["id"]))
            if rows:
                for key, value in zip(("origin", "dest", "weight", "promised"), rows[0]):
                    set_entry(w[key][0], value)
        except tk.TclError:
            pass

    w["sid"][0].bind("<FocusOut>", prefill)

    def save():
        try:
            v = read_form(w)
            if v["origin"] == v["dest"]:
                raise ValueError("Origin and destination hubs must be different.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            if not db.query("SELECT 1 FROM shipment WHERE shipment_id = %s AND shipper_id = %s",
                            (v["sid"], me["id"]))[1]:
                raise Rejected("That shipment does not exist or is not owned by you.")
            # Application-level rule: changing weight/lane of a booked shipment could overbook a departure.
            if db.query("SELECT 1 FROM booking WHERE shipment_id = %s", (v["sid"],))[1]:
                raise Rejected("This shipment is already booked onto a departure and can no longer be updated.")
            db.execute("UPDATE shipment SET origin_hub_id = %s, destination_hub_id = %s, weight_kg = %s, "
                       "promised_delivery_date = %s WHERE shipment_id = %s AND shipper_id = %s",
                       (v["origin"], v["dest"], v["weight"], v["promised"], v["sid"], me["id"]))
            return f"Shipment {v['sid']} was updated."
        run_action(action, "Shipment Updated", "Update Shipment Failed", shipper_manage)

    action_bar([("Save", save), ("Cancel", shipper_manage), ("LandingPage", shipper_landing)])


def shipper_book():
    clear_root()
    create_title("Book Shipment onto Departure")
    w = build_form([("sid", "Shipment ID", "id"), ("did", "Departure ID", "id")])
    note("Your unbooked shipments", bold=True)
    table(("id", "origin", "dest", "weight", "promised"),
          ("Shipment", "Origin", "Destination", "Weight kg", "Promised"), (90, 90, 110, 100, 120),
          db.query("SELECT s.shipment_id, s.origin_hub_id, s.destination_hub_id, s.weight_kg, "
                   "s.promised_delivery_date FROM shipment s WHERE s.shipper_id = %s AND NOT EXISTS "
                   "(SELECT 1 FROM booking b WHERE b.shipment_id = s.shipment_id) ORDER BY s.shipment_id",
                   (me["id"],))[1], height=4)
    note("Departures on the same lanes (remaining capacity)", bold=True)
    table(("dep", "origin", "dest", "time", "remaining"),
          ("Departure", "Origin", "Destination", "Date/Time", "Remaining kg"), (90, 80, 100, 160, 110),
          db.query("SELECT DISTINCT l.departure_id, l.origin_hub_id, l.destination_hub_id, "
                   "l.departure_datetime, l.remaining_kg FROM v_departure_load l "
                   "JOIN shipment s ON s.origin_hub_id = l.origin_hub_id "
                   "AND s.destination_hub_id = l.destination_hub_id "
                   "WHERE s.shipper_id = %s AND NOT EXISTS "
                   "(SELECT 1 FROM booking b WHERE b.shipment_id = s.shipment_id) "
                   "ORDER BY l.departure_datetime", (me["id"],))[1], height=5)

    def book():
        try:
            v = read_form(w)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            if not db.query("SELECT 1 FROM shipment WHERE shipment_id = %s AND shipper_id = %s",
                            (v["sid"], me["id"]))[1]:
                raise Rejected("That shipment does not exist or is not owned by you.")
            # The stored procedure checks the lane and the capacity atomically.
            results = db.call_proc("book_shipment", (v["sid"], v["did"]))
            load = ""
            if results and results[0][1]:
                row = results[0][1][0]
                load = f"\nDeparture load is now {row[2]} of {row[3]} kg."
            return f"Shipment {v['sid']} was booked onto departure {v['did']}.{load}"
        run_action(action, "Booking Successful", "Booking Rejected", shipper_manage)

    action_bar([("Book", book), ("Cancel", shipper_manage), ("LandingPage", shipper_landing)])


def shipper_track():
    tracking_page("Track Shipment", True, shipper_manage, shipper_landing)


def shipper_reports_menu():
    menu_page("Reports", "Shipper: Reports", [
        ("On-Time vs Late Summary", shipper_ontime_report),
        ("In-Transit Shipments", shipper_intransit_report),
        ("Shipments Near Promise Date", shipper_near_promise_report),
        ("GoBack", shipper_landing),
        ("LandingPage", shipper_landing),
    ])


def shipper_ontime_report():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT COUNT(*), COALESCE(SUM(s.delivery_outcome = 'ON_TIME'), 0), "
            "COALESCE(SUM(s.delivery_outcome = 'LATE'), 0) FROM shipment s "
            "JOIN scan_event e ON e.shipment_id = s.shipment_id AND e.status = 'DELIVERED' "
            "WHERE s.shipper_id = %s AND DATE(e.scan_timestamp) BETWEEN %s AND %s",
            (me["id"], start, end))
        delivered, on_time, late = rows[0]
        if not delivered:
            return [], "No delivered shipments in this date range."
        pct = lambda n: f"{round(100 * float(n) / delivered, 1)}%"
        return ([("On time", on_time, pct(on_time)), ("Late", late, pct(late))],
                f"Shipments delivered {start} to {end}: {delivered}")
    report_page("On-Time vs Late Summary", DATE_SPECS, run,
                ("outcome", "count", "pct"), ("Outcome", "Shipments", "Percent"), (200, 130, 130),
                shipper_reports_menu, shipper_landing)


IN_TRANSIT_COLS = (("id", "origin", "dest", "weight", "status", "promised", "days"),
                   ("Shipment", "Origin", "Destination", "Weight kg", "Status", "Promised", "Days to Promise"),
                   (80, 80, 100, 90, 150, 110, 120))
IN_TRANSIT_SQL = ("SELECT shipment_id, origin_hub_id, destination_hub_id, weight_kg, "
                  "COALESCE(current_status, 'NO SCANS YET'), promised_delivery_date, "
                  "DATEDIFF(promised_delivery_date, CURDATE()) FROM shipment "
                  "WHERE shipper_id = %s AND (current_status IS NULL OR current_status <> 'DELIVERED') ")


def shipper_intransit_report():
    def run(v):
        _, rows = db.query(IN_TRANSIT_SQL + "ORDER BY shipment_id", (me["id"],))
        return rows, f"{len(rows)} shipment(s) have not reached Delivered status."
    report_page("In-Transit Shipments", [], run, *IN_TRANSIT_COLS, shipper_reports_menu, shipper_landing)


def shipper_near_promise_report():
    def run(v):
        _, rows = db.query(IN_TRANSIT_SQL + "AND promised_delivery_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY) "
                           "ORDER BY promised_delivery_date, shipment_id", (me["id"], v["n"]))
        return rows, f"{len(rows)} in-transit shipment(s) overdue or due within {v['n']} day(s)."
    report_page("Shipments Near Promise Date", [("n", "N Days", "n", "7")], run, *IN_TRANSIT_COLS,
                shipper_reports_menu, shipper_landing)


# =========================================================
# CARRIER
# =========================================================

def carrier_landing():
    menu_page(f"Welcome, {me['name']}", "Carrier: Landing", [
        ("Manage Vehicles", carrier_vehicles_menu),
        ("Manage Departures", carrier_departures_menu),
        ("Post Scan Event", carrier_post_scan),
        ("Reports", carrier_reports_menu),
        ("Logout", show_home),
    ])


def type_label(vtype):
    return next(label for label, value in VEHICLE_TYPES.items() if value == vtype)


def check_type_values(vtype, v):
    if vtype == "REFRIGERATED_VAN" and v["min_temperature_c"] > v["max_temperature_c"]:
        raise ValueError("Minimum Temperature cannot be higher than Maximum Temperature.")


MY_VEHICLES_SQL = (
    "SELECT v.vehicle_id, v.vehicle_type, v.home_hub_id, CASE v.vehicle_type "
    "WHEN 'BOX_TRUCK' THEN CONCAT('Volume ', b.cargo_volume_m3, ' m3 | Rating ', b.gross_weight_rating_kg, ' kg') "
    "WHEN 'REFRIGERATED_VAN' THEN CONCAT(r.min_temperature_c, ' to ', r.max_temperature_c, ' C | Payload ', "
    "r.payload_limit_kg, ' kg') "
    "WHEN 'RAIL_CAR' THEN CONCAT(rc.axle_count, ' axles | Gauge ', rc.track_gauge_mm, ' mm') END "
    "FROM vehicle v LEFT JOIN box_truck b ON b.vehicle_id = v.vehicle_id "
    "LEFT JOIN refrigerated_van r ON r.vehicle_id = v.vehicle_id "
    "LEFT JOIN rail_car rc ON rc.vehicle_id = v.vehicle_id "
    "WHERE v.carrier_id = %s ORDER BY v.vehicle_id")
MY_VEHICLES_COLS = (("id", "type", "hub", "details"), ("Vehicle ID", "Type", "Home Hub", "Details"),
                    (90, 160, 90, 420))


def carrier_vehicles_menu():
    menu_page("Manage Vehicles", "Carrier: Manage Vehicles", [
        ("Add New Vehicle", carrier_add_vehicle),
        ("Update Vehicle", carrier_update_vehicle),
        ("View Vehicles", carrier_view_vehicles),
        ("GoBack", carrier_landing),
        ("LandingPage", carrier_landing),
    ])


def carrier_view_vehicles():
    def run(v):
        _, rows = db.query(MY_VEHICLES_SQL, (me["id"],))
        return rows, f"{len(rows)} vehicle(s)"
    report_page("My Vehicles", [], run, *MY_VEHICLES_COLS, carrier_vehicles_menu, carrier_landing)


def carrier_add_vehicle():
    clear_root()
    create_title("Add New Vehicle", "Common details")
    w = build_form([("vid", "Vehicle ID (blank = assign automatically)", "id_opt"),
                    ("hub", "Home Hub ID", "hub"),
                    ("vtype", "Vehicle Type", "choice", "", list(VEHICLE_TYPES))])
    note("Hubs: " + ", ".join(get_hubs()))

    def cont():
        try:
            v = read_form(w)
            if v["vid"] is not None and db.query("SELECT 1 FROM vehicle WHERE vehicle_id = %s", (v["vid"],))[1]:
                raise ValueError(f"Vehicle ID {v['vid']} already exists.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return
        except Exception as e:
            messagebox.showerror("Database Error", err_text(e))
            return
        carrier_add_vehicle_details(v["vid"], v["hub"], VEHICLE_TYPES[v["vtype"]])

    action_bar([("Continue", cont), ("GoBack", carrier_vehicles_menu), ("LandingPage", carrier_landing)])


def carrier_add_vehicle_details(vid, hub, vtype):
    table_name, attrs = TYPE_DETAILS[vtype]
    clear_root()
    create_title(f"Add {type_label(vtype)} Details", f"Home hub {hub}")
    w = build_form([(c, label, kind) for c, label, kind in attrs])

    def save():
        try:
            v = read_form(w)
            check_type_values(vtype, v)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            cols = [c for c, _, _ in attrs]
            with db.transaction() as cur:       # vehicle row + subtype row, all or nothing
                if vid is None:
                    cur.execute("INSERT INTO vehicle (carrier_id, home_hub_id, vehicle_type) VALUES (%s, %s, %s)",
                                (me["id"], hub, vtype))
                    new_id = cur.lastrowid
                else:
                    cur.execute("INSERT INTO vehicle (vehicle_id, carrier_id, home_hub_id, vehicle_type) "
                                "VALUES (%s, %s, %s, %s)", (vid, me["id"], hub, vtype))
                    new_id = vid
                cur.execute(f"INSERT INTO {table_name} (vehicle_id, {', '.join(cols)}) "
                            f"VALUES (%s{', %s' * len(cols)})", [new_id] + [v[c] for c in cols])
            return f"Vehicle {new_id} ({type_label(vtype)}) was added."
        run_action(action, "Vehicle Added", "Add Vehicle Failed", carrier_vehicles_menu)

    action_bar([("Save", save), ("Cancel", carrier_add_vehicle), ("LandingPage", carrier_landing)])


def carrier_update_vehicle():
    clear_root()
    create_title("Update Vehicle")
    w = build_form([("vid", "Vehicle ID", "id")])
    table(*MY_VEHICLES_COLS, rows=db.query(MY_VEHICLES_SQL, (me["id"],))[1], height=8)

    def go(kind):
        try:
            v = read_form(w)
            _, rows = db.query("SELECT vehicle_type, home_hub_id FROM vehicle "
                               "WHERE vehicle_id = %s AND carrier_id = %s", (v["vid"], me["id"]))
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return
        except Exception as e:
            messagebox.showerror("Database Error", err_text(e))
            return
        if not rows:
            messagebox.showerror("Not Allowed", "That vehicle does not exist or is not owned by your carrier account.")
            return
        vtype, hub = rows[0]
        if kind == "common":
            carrier_update_common(v["vid"], hub)
        else:
            carrier_update_type(v["vid"], vtype)

    action_bar([("Update Common Details", lambda: go("common")), ("Update Type Details", lambda: go("type")),
                ("GoBack", carrier_vehicles_menu), ("LandingPage", carrier_landing)])


def carrier_update_common(vid, hub):
    clear_root()
    create_title(f"Update Vehicle {vid}", "Common details")
    w = build_form([("hub", "Home Hub ID", "hub", hub)])
    note("Hubs: " + ", ".join(get_hubs()))

    def save():
        try:
            v = read_form(w)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            db.execute("UPDATE vehicle SET home_hub_id = %s WHERE vehicle_id = %s AND carrier_id = %s",
                       (v["hub"], vid, me["id"]))
            return f"Vehicle {vid} now has home hub {v['hub']}."
        run_action(action, "Vehicle Updated", "Update Vehicle Failed", carrier_vehicles_menu)

    action_bar([("Save", save), ("Cancel", carrier_update_vehicle), ("LandingPage", carrier_landing)])


def carrier_update_type(vid, vtype):
    table_name, attrs = TYPE_DETAILS[vtype]
    cols = [c for c, _, _ in attrs]
    _, rows = db.query(f"SELECT {', '.join(cols)} FROM {table_name} WHERE vehicle_id = %s", (vid,))
    clear_root()
    create_title(f"Update Vehicle {vid}", f"{type_label(vtype)} details")
    w = build_form([(c, label, kind, rows[0][i]) for i, (c, label, kind) in enumerate(attrs)])

    def save():
        try:
            v = read_form(w)
            check_type_values(vtype, v)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            sets = ", ".join(f"{c} = %s" for c in cols)
            db.execute(f"UPDATE {table_name} SET {sets} WHERE vehicle_id = %s "
                       f"AND EXISTS (SELECT 1 FROM vehicle WHERE vehicle_id = %s AND carrier_id = %s)",
                       [v[c] for c in cols] + [vid, vid, me["id"]])
            return f"Vehicle {vid} details were updated."
        run_action(action, "Vehicle Updated", "Update Vehicle Failed", carrier_vehicles_menu)

    action_bar([("Save", save), ("Cancel", carrier_update_vehicle), ("LandingPage", carrier_landing)])


# ---------- departures ----------

def carrier_departures_menu():
    menu_page("Manage Departures", "Carrier: Manage Departures", [
        ("Schedule Departure", carrier_schedule_departure),
        ("Update Departure", carrier_update_departure),
        ("View Departures", carrier_view_departures),
        ("GoBack", carrier_landing),
        ("LandingPage", carrier_landing),
    ])


MY_DEPARTURES_SQL = (
    "SELECT l.departure_id, l.vehicle_id, l.origin_hub_id, l.destination_hub_id, l.departure_datetime, "
    "l.maximum_weight_kg, l.booked_weight_kg, l.remaining_kg FROM v_departure_load l "
    "JOIN vehicle v ON v.vehicle_id = l.vehicle_id WHERE v.carrier_id = %s ORDER BY l.departure_id")
MY_DEPARTURES_COLS = (("id", "vehicle", "origin", "dest", "time", "cap", "booked", "remaining"),
                      ("Departure", "Vehicle", "Origin", "Destination", "Date/Time", "Capacity kg",
                       "Booked kg", "Remaining kg"), (80, 70, 70, 90, 150, 100, 90, 100))


def vehicle_weight_limit(vehicle_id):
    """Application-level rule: a departure's capacity cannot exceed what the vehicle can carry."""
    _, rows = db.query(
        "SELECT COALESCE(b.gross_weight_rating_kg, r.payload_limit_kg) FROM vehicle v "
        "LEFT JOIN box_truck b ON b.vehicle_id = v.vehicle_id "
        "LEFT JOIN refrigerated_van r ON r.vehicle_id = v.vehicle_id WHERE v.vehicle_id = %s", (vehicle_id,))
    return rows[0][0] if rows and rows[0][0] is not None else None     # rail cars: no limit stored


def owns_vehicle(vehicle_id):
    return bool(db.query("SELECT 1 FROM vehicle WHERE vehicle_id = %s AND carrier_id = %s",
                         (vehicle_id, me["id"]))[1])


def carrier_view_departures():
    def run(v):
        _, rows = db.query(MY_DEPARTURES_SQL, (me["id"],))
        return rows, f"{len(rows)} departure(s)"
    report_page("My Departures", [], run, *MY_DEPARTURES_COLS, carrier_departures_menu, carrier_landing)


def carrier_schedule_departure():
    clear_root()
    create_title("Schedule Departure")
    w = build_form([("vid", "Vehicle ID", "id"), ("origin", "Origin Hub ID", "hub"),
                    ("dest", "Destination Hub ID", "hub"),
                    ("when", "Departure Date/Time (YYYY-MM-DD HH:MM)", "datetime"),
                    ("cap", "Capacity (max total weight, kg)", "dec")])
    note("Hubs: " + ", ".join(get_hubs()))
    table(*MY_VEHICLES_COLS, rows=db.query(MY_VEHICLES_SQL, (me["id"],))[1], height=5)

    def save():
        try:
            v = read_form(w)
            if v["origin"] == v["dest"]:
                raise ValueError("Origin and destination hubs must be different.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            if not owns_vehicle(v["vid"]):
                raise Rejected("That vehicle does not exist or is not owned by your carrier account.")
            limit = vehicle_weight_limit(v["vid"])
            if limit is not None and v["cap"] > limit:
                raise Rejected(f"This vehicle can carry at most {limit} kg.")
            new_id = db.execute(
                "INSERT INTO departure (vehicle_id, origin_hub_id, destination_hub_id, departure_datetime, "
                "maximum_weight_kg) VALUES (%s, %s, %s, %s, %s)",
                (v["vid"], v["origin"], v["dest"], v["when"], v["cap"]))
            return f"Departure {new_id} was scheduled. Remaining capacity: {v['cap']} kg."
        run_action(action, "Departure Scheduled", "Schedule Departure Failed", carrier_departures_menu)

    action_bar([("Save", save), ("Cancel", carrier_departures_menu), ("LandingPage", carrier_landing)])


def carrier_update_departure():
    clear_root()
    create_title("Update Departure")
    w = build_form([("did", "Departure ID", "id"), ("vid", "Vehicle ID", "id"),
                    ("origin", "Origin Hub ID", "hub"), ("dest", "Destination Hub ID", "hub"),
                    ("when", "Departure Date/Time (YYYY-MM-DD HH:MM)", "datetime"),
                    ("cap", "Capacity (max total weight, kg)", "dec")])
    note("Enter a Departure ID and press Tab to load its current values.")
    table(*MY_DEPARTURES_COLS, rows=db.query(MY_DEPARTURES_SQL, (me["id"],))[1], height=6)

    def prefill(event=None):
        try:
            text = w["did"][0].get().strip()
            if not text.isdigit():
                return
            _, rows = db.query(
                "SELECT l.vehicle_id, l.origin_hub_id, l.destination_hub_id, l.departure_datetime, "
                "l.maximum_weight_kg FROM v_departure_load l JOIN vehicle v ON v.vehicle_id = l.vehicle_id "
                "WHERE l.departure_id = %s AND v.carrier_id = %s", (int(text), me["id"]))
            if rows:
                for key, value in zip(("vid", "origin", "dest", "when", "cap"), rows[0]):
                    set_entry(w[key][0], value)
        except tk.TclError:
            pass

    w["did"][0].bind("<FocusOut>", prefill)

    def save():
        try:
            v = read_form(w)
            if v["origin"] == v["dest"]:
                raise ValueError("Origin and destination hubs must be different.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            _, rows = db.query(
                "SELECT l.origin_hub_id, l.destination_hub_id, l.booked_weight_kg FROM v_departure_load l "
                "JOIN vehicle v ON v.vehicle_id = l.vehicle_id WHERE l.departure_id = %s AND v.carrier_id = %s",
                (v["did"], me["id"]))
            if not rows:
                raise Rejected("That departure does not exist or is not operated by your carrier account.")
            old_origin, old_dest, booked = rows[0]
            if not owns_vehicle(v["vid"]):
                raise Rejected("That vehicle does not exist or is not owned by your carrier account.")
            if v["cap"] < booked:
                raise Rejected(f"Capacity cannot be lowered below the {booked} kg already booked.")
            if booked > 0 and (v["origin"] != old_origin or v["dest"] != old_dest):
                raise Rejected("The lane cannot be changed once shipments are booked on this departure.")
            limit = vehicle_weight_limit(v["vid"])
            if limit is not None and v["cap"] > limit:
                raise Rejected(f"This vehicle can carry at most {limit} kg.")
            db.execute("UPDATE departure SET vehicle_id = %s, origin_hub_id = %s, destination_hub_id = %s, "
                       "departure_datetime = %s, maximum_weight_kg = %s WHERE departure_id = %s",
                       (v["vid"], v["origin"], v["dest"], v["when"], v["cap"], v["did"]))
            return f"Departure {v['did']} was updated."
        run_action(action, "Departure Updated", "Update Departure Failed", carrier_departures_menu)

    action_bar([("Save", save), ("Cancel", carrier_departures_menu), ("LandingPage", carrier_landing)])


# ---------- scans ----------

def carrier_post_scan():
    clear_root()
    create_title("Post Scan Event")
    w = build_form([("sid", "Shipment ID", "id"), ("did", "Departure ID", "id"),
                    ("when", "Timestamp (YYYY-MM-DD HH:MM)", "datetime", datetime.now().strftime("%Y-%m-%d %H:%M")),
                    ("hub", "Hub ID", "hub"),
                    ("status", "Status", "choice", "", list(STATUS_CHOICES))])
    note("Hubs: " + ", ".join(get_hubs()))
    note("Shipments booked on your departures", bold=True)
    table(("sid", "dep", "origin", "dest", "status"),
          ("Shipment", "Departure", "Origin", "Destination", "Current Status"), (90, 90, 80, 100, 160),
          db.query("SELECT s.shipment_id, b.departure_id, s.origin_hub_id, s.destination_hub_id, "
                   "COALESCE(s.current_status, 'NO SCANS YET') FROM booking b "
                   "JOIN shipment s ON s.shipment_id = b.shipment_id "
                   "JOIN departure d ON d.departure_id = b.departure_id "
                   "JOIN vehicle v ON v.vehicle_id = d.vehicle_id WHERE v.carrier_id = %s "
                   "ORDER BY s.shipment_id", (me["id"],))[1], height=6)

    def save():
        try:
            v = read_form(w)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def action():
            if not db.query("SELECT 1 FROM departure d JOIN vehicle v ON v.vehicle_id = d.vehicle_id "
                            "WHERE d.departure_id = %s AND v.carrier_id = %s", (v["did"], me["id"]))[1]:
                raise Rejected("That departure does not exist or is not operated by your carrier account.")
            if not db.query("SELECT 1 FROM booking WHERE shipment_id = %s AND departure_id = %s",
                            (v["sid"], v["did"]))[1]:
                raise Rejected(f"Shipment {v['sid']} is not booked on departure {v['did']}, "
                               f"so you are not authorized to scan it.")
            status = STATUS_CHOICES[v["status"]]
            # Next sequence number is computed inside the INSERT; the database triggers enforce
            # chronology / status order and update the shipment's status and on-time flag.
            db.execute("INSERT INTO scan_event (shipment_id, scan_sequence_no, scan_timestamp, hub_id, status) "
                       "SELECT %s, COALESCE(MAX(scan_sequence_no), 0) + 1, %s, %s, %s "
                       "FROM scan_event WHERE shipment_id = %s",
                       (v["sid"], v["when"], v["hub"], status, v["sid"]))
            _, r = db.query("SELECT current_status, COALESCE(delivery_outcome, '-') FROM shipment "
                            "WHERE shipment_id = %s", (v["sid"],))
            return f"Scan recorded.\nShipment {v['sid']} status: {r[0][0]}   Outcome: {r[0][1]}"
        run_action(action, "Scan Posted", "Scan Rejected", carrier_landing)

    action_bar([("Save", save), ("Cancel", carrier_landing), ("LandingPage", carrier_landing)])


# ---------- carrier reports ----------

def carrier_reports_menu():
    menu_page("Reports", "Carrier: Reports", [
        ("Load per Departure", carrier_load_report),
        ("Carrier On-Time Rate", carrier_ontime_report),
        ("Carrier Shipment Dwell Time", carrier_dwell_report),
        ("GoBack", carrier_landing),
        ("LandingPage", carrier_landing),
    ])


def carrier_load_report():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT l.departure_id, l.origin_hub_id, l.destination_hub_id, l.departure_datetime, "
            "l.maximum_weight_kg, l.booked_weight_kg, l.remaining_kg, l.utilization_pct "
            "FROM v_departure_load l JOIN vehicle v ON v.vehicle_id = l.vehicle_id "
            "WHERE v.carrier_id = %s AND DATE(l.departure_datetime) BETWEEN %s AND %s "
            "ORDER BY l.departure_datetime", (me["id"], start, end))
        return rows, f"{len(rows)} departure(s) between {start} and {end}"
    report_page("Load per Departure", DATE_SPECS, run,
                ("id", "origin", "dest", "time", "cap", "booked", "remaining", "pct"),
                ("Departure", "Origin", "Destination", "Date/Time", "Capacity kg", "Booked kg",
                 "Remaining kg", "Percent Full"), (80, 70, 90, 150, 100, 90, 100, 100),
                carrier_reports_menu, carrier_landing)


def carrier_ontime_report():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT COUNT(*), COALESCE(SUM(s.delivery_outcome = 'ON_TIME'), 0), "
            "COALESCE(SUM(s.delivery_outcome = 'LATE'), 0) FROM shipment s "
            "JOIN scan_event e ON e.shipment_id = s.shipment_id AND e.status = 'DELIVERED' "
            "JOIN booking b ON b.shipment_id = s.shipment_id "
            "JOIN departure d ON d.departure_id = b.departure_id "
            "JOIN vehicle v ON v.vehicle_id = d.vehicle_id "
            "WHERE v.carrier_id = %s AND DATE(e.scan_timestamp) BETWEEN %s AND %s",
            (me["id"], start, end))
        delivered, on_time, late = rows[0]
        if not delivered:
            return [], "No delivered shipments in this date range."
        rate = round(100 * float(on_time) / delivered, 1)
        return [(delivered, on_time, late, f"{rate}%")], f"On-time delivery rate {start} to {end}: {rate}%"
    report_page("Carrier On-Time Rate", DATE_SPECS, run,
                ("delivered", "ontime", "late", "rate"),
                ("Delivered", "On Time", "Late", "On-Time Rate"), (120, 120, 120, 140),
                carrier_reports_menu, carrier_landing)


def carrier_dwell_report():
    def run(v):
        if not db.query("SELECT 1 FROM booking b JOIN departure d ON d.departure_id = b.departure_id "
                        "JOIN vehicle v ON v.vehicle_id = d.vehicle_id "
                        "WHERE b.shipment_id = %s AND v.carrier_id = %s", (v["sid"], me["id"]))[1]:
            raise Rejected("Your carrier account did not handle that shipment (or it does not exist).")
        _, rows = db.query(DWELL_SQL, (v["sid"],))
        return rows, f"Scan history of shipment {v['sid']}: {len(rows)} scan(s)"
    report_page("Carrier Shipment Dwell Time", [("sid", "Shipment ID", "id")], run, *DWELL_COLS,
                carrier_reports_menu, carrier_landing)


# =========================================================
# VIEWER (read-only: only SELECT statements below)
# =========================================================

def viewer_landing():
    menu_page(f"Welcome, {me['name']}", "Viewer: Landing", [
        ("Track Shipment", viewer_track),
        ("Published Performance Reports", viewer_reports_menu),
        ("Logout", show_home),
    ])


def viewer_track():
    tracking_page("Track Shipment", False, viewer_landing, viewer_landing)


def viewer_reports_menu():
    menu_page("Published Performance Reports", "Viewer: Published Performance Reports", [
        ("On-Time Rates by Lane", viewer_ontime_by_lane),
        ("On-Time Rates by Carrier", viewer_ontime_by_carrier),
        ("Lane Volume Ranking", viewer_lane_volume),
        ("Top Departures per Lane", viewer_top_departures),
        ("Shipment Dwell Time", viewer_dwell),
        ("Running Total Deliveries by Carrier", viewer_running_total),
        ("At-Risk In-Transit Shipments", viewer_at_risk),
        ("GoBack", viewer_landing),
        ("LandingPage", viewer_landing),
    ])


def viewer_ontime_by_lane():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT s.origin_hub_id, s.destination_hub_id, COUNT(*), SUM(s.delivery_outcome = 'ON_TIME'), "
            "SUM(s.delivery_outcome = 'LATE'), ROUND(100 * SUM(s.delivery_outcome = 'ON_TIME') / COUNT(*), 1), "
            "ROUND(100 * SUM(s.delivery_outcome = 'LATE') / COUNT(*), 1) FROM shipment s "
            "JOIN scan_event e ON e.shipment_id = s.shipment_id AND e.status = 'DELIVERED' "
            "WHERE DATE(e.scan_timestamp) BETWEEN %s AND %s "
            "GROUP BY s.origin_hub_id, s.destination_hub_id ORDER BY s.origin_hub_id, s.destination_hub_id",
            (start, end))
        return rows, f"Deliveries completed {start} to {end}, grouped by lane"
    report_page("On-Time Rates by Lane", DATE_SPECS, run,
                ("o", "d", "n", "on", "late", "onp", "lp"),
                ("Origin", "Destination", "Delivered", "On Time", "Late", "On-Time %", "Late %"),
                (90, 110, 90, 90, 80, 100, 90), viewer_reports_menu, viewer_landing)


def viewer_ontime_by_carrier():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT RANK() OVER (ORDER BY t.on_time_pct DESC), t.account_id, t.carrier_name, t.delivered, "
            "t.on_time, t.late, t.on_time_pct FROM ("
            "SELECT c.account_id, c.carrier_name, COUNT(*) AS delivered, "
            "SUM(s.delivery_outcome = 'ON_TIME') AS on_time, SUM(s.delivery_outcome = 'LATE') AS late, "
            "ROUND(100 * SUM(s.delivery_outcome = 'ON_TIME') / COUNT(*), 1) AS on_time_pct FROM shipment s "
            "JOIN scan_event e ON e.shipment_id = s.shipment_id AND e.status = 'DELIVERED' "
            "JOIN booking b ON b.shipment_id = s.shipment_id "
            "JOIN departure d ON d.departure_id = b.departure_id "
            "JOIN vehicle v ON v.vehicle_id = d.vehicle_id JOIN carrier c ON c.account_id = v.carrier_id "
            "WHERE DATE(e.scan_timestamp) BETWEEN %s AND %s GROUP BY c.account_id, c.carrier_name) t "
            "ORDER BY 1, t.account_id", (start, end))
        return rows, f"Carriers ranked by on-time rate, deliveries {start} to {end}"
    report_page("On-Time Rates by Carrier", DATE_SPECS, run,
                ("rank", "id", "name", "n", "on", "late", "pct"),
                ("Rank", "Carrier ID", "Carrier", "Delivered", "On Time", "Late", "On-Time %"),
                (60, 90, 220, 90, 90, 80, 100), viewer_reports_menu, viewer_landing)


def viewer_lane_volume():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT RANK() OVER (ORDER BY SUM(weight_kg) DESC), origin_hub_id, destination_hub_id, COUNT(*), "
            "SUM(weight_kg) FROM shipment WHERE promised_delivery_date BETWEEN %s AND %s "
            "GROUP BY origin_hub_id, destination_hub_id ORDER BY 1, origin_hub_id, destination_hub_id",
            (start, end))
        return rows, f"Lanes ranked by total shipment weight (promised delivery date {start} to {end})"
    report_page("Lane Volume Ranking", DATE_SPECS, run,
                ("rank", "o", "d", "n", "kg"), ("Rank", "Origin", "Destination", "Shipments", "Total kg"),
                (70, 100, 120, 100, 120), viewer_reports_menu, viewer_landing)


def viewer_top_departures():
    def run(v):
        start, end = date_range(v)
        _, rows = db.query(
            "SELECT * FROM (SELECT origin_hub_id, destination_hub_id, departure_id, departure_datetime, "
            "booked_weight_kg, maximum_weight_kg, utilization_pct, RANK() OVER (PARTITION BY origin_hub_id, "
            "destination_hub_id ORDER BY booked_weight_kg DESC) AS lane_rank FROM v_departure_load "
            "WHERE DATE(departure_datetime) BETWEEN %s AND %s) r WHERE lane_rank <= %s "
            "ORDER BY origin_hub_id, destination_hub_id, lane_rank, departure_id", (start, end, v["n"]))
        return rows, f"Top {v['n']} departures per lane by booked load, {start} to {end}"
    report_page("Top Departures per Lane", DATE_SPECS + [("n", "Top N", "id", "3")], run,
                ("o", "d", "dep", "time", "booked", "max", "pct", "rank"),
                ("Origin", "Destination", "Departure", "Date/Time", "Booked kg", "Capacity kg", "Percent Full",
                 "Rank"), (70, 90, 80, 150, 90, 100, 100, 60), viewer_reports_menu, viewer_landing)


def viewer_dwell():
    def run(v):
        _, rows = db.query(DWELL_SQL, (v["sid"],))
        if not rows:
            raise Rejected("That shipment does not exist or has no scan events.")
        return rows, f"Scan history of shipment {v['sid']}: {len(rows)} scan(s)"
    report_page("Shipment Dwell Time", [("sid", "Shipment ID", "id")], run, *DWELL_COLS,
                viewer_reports_menu, viewer_landing)


def viewer_running_total():
    def run(v):
        start, end = date_range(v)
        cid = v["cid"]
        if cid is not None and not db.query("SELECT 1 FROM carrier WHERE account_id = %s", (cid,))[1]:
            raise ValueError(f"Carrier ID {cid} does not exist.")
        _, rows = db.query(
            "WITH w AS (SELECT v.carrier_id, DATE_SUB(DATE(e.scan_timestamp), INTERVAL WEEKDAY(e.scan_timestamp) DAY) "
            "AS week_start, COUNT(*) AS delivered FROM scan_event e "
            "JOIN booking b ON b.shipment_id = e.shipment_id "
            "JOIN departure d ON d.departure_id = b.departure_id JOIN vehicle v ON v.vehicle_id = d.vehicle_id "
            "WHERE e.status = 'DELIVERED' AND DATE(e.scan_timestamp) BETWEEN %s AND %s "
            "AND (%s IS NULL OR v.carrier_id = %s) GROUP BY v.carrier_id, week_start) "
            "SELECT w.carrier_id, c.carrier_name, w.week_start, w.delivered, SUM(w.delivered) OVER "
            "(PARTITION BY w.carrier_id ORDER BY w.week_start ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) "
            "FROM w JOIN carrier c ON c.account_id = w.carrier_id ORDER BY w.carrier_id, w.week_start",
            (start, end, cid, cid))
        return rows, f"Cumulative delivered shipments by week, {start} to {end}"
    report_page("Running Total Deliveries by Carrier",
                DATE_SPECS + [("cid", "Carrier ID (optional)", "id_opt")], run,
                ("id", "name", "week", "n", "total"),
                ("Carrier ID", "Carrier", "Week Starting", "Delivered That Week", "Running Total"),
                (90, 220, 120, 150, 120), viewer_reports_menu, viewer_landing)


def viewer_at_risk():
    def run(v):
        _, rows = db.query(
            "SELECT s.shipment_id, sh.shipper_name, s.origin_hub_id, s.destination_hub_id, "
            "COALESCE(s.current_status, 'NO SCANS YET'), s.promised_delivery_date, "
            "DATEDIFF(s.promised_delivery_date, CURDATE()) FROM shipment s "
            "JOIN shipper sh ON sh.account_id = s.shipper_id "
            "WHERE (s.current_status IS NULL OR s.current_status <> 'DELIVERED') "
            "AND s.promised_delivery_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY s.promised_delivery_date, s.shipment_id", (v["n"],))
        return rows, f"{len(rows)} in-transit shipment(s) overdue or due within {v['n']} day(s)"
    report_page("At-Risk In-Transit Shipments", [("n", "N Days", "n", "7")], run,
                ("id", "shipper", "o", "d", "status", "promised", "days"),
                ("Shipment", "Shipper", "Origin", "Destination", "Status", "Promised", "Days to Promise"),
                (80, 190, 70, 100, 140, 110, 120), viewer_reports_menu, viewer_landing)


# =========================================================
# VIEW QUERIES (root menu, the 6 required analytical queries, numbered as in the handout)
# =========================================================

def show_queries_menu():
    menu_page("View Queries", "Select a query to run", [
        ("Number of vehicles of each type per carrier", query1),
        ("Departures ranked by weight utilization per lane", query2),
        ("Dwell time between consecutive scans of a shipment", query3),
        ("Running total of delivered weight by week per carrier", query4),
        ("Departures carrying shipments of 2+ different shippers", query5),
        ("Shipments with no scan events", query6),
        ("Back", show_home),
    ])


def query_page(heading, specs, run, columns, headings, widths):
    report_page(heading, specs, run, columns, headings, widths, show_queries_menu, show_home,
                run_label="Run Query", back_label="Back", landing_label="Home")


def query1():
    def run(v):
        _, rows = db.query(
            "SELECT c.account_id, c.carrier_name, v.vehicle_type, COUNT(*) FROM carrier c "
            "JOIN vehicle v ON v.carrier_id = c.account_id GROUP BY c.account_id, c.carrier_name, v.vehicle_type "
            "ORDER BY c.account_id, v.vehicle_type")
        return rows, ""
    query_page("Query 1 - Vehicles per Type per Carrier", [], run,
               ("id", "name", "type", "n"), ("Carrier ID", "Carrier", "Vehicle Type", "Vehicle Count"),
               (90, 230, 180, 120))


def query2():
    def run(v):
        top = v["n"] if v["n"] else 10 ** 9
        _, rows = db.query(
            "SELECT * FROM (SELECT origin_hub_id, destination_hub_id, departure_id, departure_datetime, "
            "booked_weight_kg, maximum_weight_kg, utilization_pct, RANK() OVER (PARTITION BY origin_hub_id, "
            "destination_hub_id ORDER BY utilization_pct DESC) AS lane_rank FROM v_departure_load) r "
            "WHERE lane_rank <= %s ORDER BY origin_hub_id, destination_hub_id, lane_rank, departure_id", (top,))
        return rows, "Rank 1 = most heavily loaded departure on the lane"
    query_page("Query 2 - Departures Ranked by Utilization per Lane", [("n", "Top N per lane (blank = all)", "id_opt")],
               run, ("o", "d", "dep", "time", "booked", "max", "util", "rank"),
               ("Origin", "Destination", "Departure", "Date/Time", "Booked kg", "Capacity kg", "Utilization %",
                "Rank"), (70, 90, 80, 150, 90, 100, 110, 60))


def query3():
    def run(v):
        _, rows = db.query(DWELL_SQL, (v["sid"],))
        return rows, f"Scan history of shipment {v['sid']}"
    query_page("Query 3 - Time Between Consecutive Scans", [("sid", "Shipment ID", "id")], run, *DWELL_COLS)


def query4():
    def run(v):
        _, rows = db.query(
            "WITH delivered AS (SELECT v.carrier_id, DATE_SUB(DATE(sc.scan_timestamp), "
            "INTERVAL WEEKDAY(sc.scan_timestamp) DAY) AS week_start, s.weight_kg FROM scan_event sc "
            "JOIN shipment s ON s.shipment_id = sc.shipment_id JOIN booking b ON b.shipment_id = s.shipment_id "
            "JOIN departure d ON d.departure_id = b.departure_id JOIN vehicle v ON v.vehicle_id = d.vehicle_id "
            "WHERE sc.status = 'DELIVERED'), weekly AS (SELECT carrier_id, week_start, SUM(weight_kg) AS "
            "delivered_kg FROM delivered GROUP BY carrier_id, week_start) "
            "SELECT w.carrier_id, c.carrier_name, w.week_start, w.delivered_kg, SUM(w.delivered_kg) OVER "
            "(PARTITION BY w.carrier_id ORDER BY w.week_start ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) "
            "FROM weekly w JOIN carrier c ON c.account_id = w.carrier_id ORDER BY w.carrier_id, w.week_start")
        return rows, "Delivered weight per week (weeks start Monday) with running total"
    query_page("Query 4 - Running Delivered Weight by Carrier", [], run,
               ("id", "name", "week", "kg", "total"),
               ("Carrier ID", "Carrier", "Week Starting", "Delivered kg", "Running Total kg"),
               (90, 230, 120, 120, 140))


def query5():
    def run(v):
        _, rows = db.query(
            "SELECT b.departure_id, COUNT(DISTINCT s.shipper_id) FROM booking b "
            "JOIN shipment s ON s.shipment_id = b.shipment_id GROUP BY b.departure_id "
            "HAVING COUNT(DISTINCT s.shipper_id) >= 2 ORDER BY b.departure_id")
        return rows, ""
    query_page("Query 5 - Departures with 2+ Different Shippers", [], run,
               ("dep", "n"), ("Departure ID", "Distinct Shippers"), (160, 180))


def query6():
    def run(v):
        _, rows = db.query(
            "SELECT s.shipment_id, s.shipper_id, sh.shipper_name, s.origin_hub_id, s.destination_hub_id, "
            "s.promised_delivery_date FROM shipment s JOIN shipper sh ON sh.account_id = s.shipper_id "
            "WHERE NOT EXISTS (SELECT 1 FROM scan_event e WHERE e.shipment_id = s.shipment_id) "
            "ORDER BY s.shipment_id")
        return rows, ""
    query_page("Query 6 - Shipments With No Scan Events", [], run,
               ("id", "shipper", "name", "o", "d", "promised"),
               ("Shipment ID", "Shipper ID", "Shipper", "Origin", "Destination", "Promised Delivery"),
               (100, 100, 220, 80, 110, 130))


# =========================================================
# START APPLICATION
# =========================================================

def main():
    global root
    root = tk.Tk()
    root.title("Freight Tracking and Delivery Management")
    root.geometry("1100x750")
    root.minsize(900, 650)
    try:
        db.query("SELECT 1")
    except Exception as e:
        messagebox.showerror("Cannot Connect to the Database", err_text(e))
        root.destroy()
        return
    show_home()
    root.mainloop()


if __name__ == "__main__":
    main()