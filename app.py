import hashlib
import os
import sqlite3
from datetime import date, datetime

import pandas as pd
import streamlit as st

DB_PATH = "crime_system.db"
EVIDENCE_DIR = "evidence_files"
os.makedirs(EVIDENCE_DIR, exist_ok=True)

st.set_page_config(page_title="Crime Investigation System", page_icon="🕵️", layout="wide")

CASE_TYPES = ["Theft", "Robbery", "Assault", "Fraud", "Homicide", "Cybercrime", "Kidnapping", "Narcotics", "Other"]
STATUSES = ["Open", "Under Investigation", "Suspect Identified", "Court Proceedings", "Closed"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]


# ---------- Database ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cases(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_no TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            case_type TEXT,
            location TEXT,
            incident_date TEXT,
            description TEXT,
            status TEXT DEFAULT 'Open',
            priority TEXT DEFAULT 'Medium',
            assigned_to TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS suspects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            name TEXT,
            age INTEGER,
            address TEXT,
            description TEXT,
            status TEXT DEFAULT 'Person of Interest',
            FOREIGN KEY(case_id) REFERENCES cases(id)
        );
        CREATE TABLE IF NOT EXISTS evidence(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            item TEXT,
            description TEXT,
            collected_by TEXT,
            collected_at TEXT,
            file_path TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(id)
        );
        CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            author TEXT,
            note TEXT,
            created_at TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(id)
        );
        """
    )
    # Default admin account (change the password after first login!)
    if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        salt = os.urandom(8).hex()
        c.execute(
            "INSERT INTO users(username, full_name, role, salt, password_hash) VALUES(?,?,?,?,?)",
            ("admin", "System Administrator", "Admin", salt, hash_pw("admin123", salt)),
        )
    conn.commit()
    conn.close()


def query(sql, params=()):
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def execute(sql, params=()):
    conn = get_conn()
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def df(sql, params=()):
    conn = get_conn()
    data = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return data


# ---------- Auth ----------
def login_page():
    st.title("🕵️ Crime Investigation Management System")
    st.subheader("Officer Login")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Login")
    if ok:
        rows = query("SELECT * FROM users WHERE username=?", (username,))
        if rows and hash_pw(password, rows[0]["salt"]) == rows[0]["password_hash"]:
            st.session_state.user = dict(rows[0])
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.caption("First time? Default login is admin / admin123. Change it immediately.")


def is_admin():
    return st.session_state.user["role"] == "Admin"


# ---------- Pages ----------
def dashboard():
    st.header("📊 Dashboard")
    cases = df("SELECT * FROM cases")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases", len(cases))
    c2.metric("Open / Active", int((cases["status"] != "Closed").sum()) if len(cases) else 0)
    c3.metric("Closed", int((cases["status"] == "Closed").sum()) if len(cases) else 0)
    c4.metric("Critical Priority", int((cases["priority"] == "Critical").sum()) if len(cases) else 0)

    if len(cases):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Cases by Status")
            st.bar_chart(cases["status"].value_counts())
        with col2:
            st.subheader("Cases by Type")
            st.bar_chart(cases["case_type"].value_counts())
        st.subheader("Recent Cases")
        st.dataframe(
            cases.sort_values("id", ascending=False).head(10)[
                ["case_no", "title", "case_type", "status", "priority", "assigned_to"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No cases yet. Register one from 'New Case'.")


def new_case():
    st.header("➕ Register New Case")
    officers = [r["username"] for r in query("SELECT username FROM users")]
    with st.form("new_case"):
        title = st.text_input("Case Title *")
        col1, col2 = st.columns(2)
        case_type = col1.selectbox("Crime Type", CASE_TYPES)
        priority = col2.selectbox("Priority", PRIORITIES, index=1)
        location = col1.text_input("Location")
        inc_date = col2.date_input("Incident Date", value=date.today())
        assigned = st.selectbox("Assign To", officers)
        desc = st.text_area("Description", height=150)
        ok = st.form_submit_button("Create Case")
    if ok:
        if not title.strip():
            st.error("Title is required.")
            return
        count = query("SELECT COUNT(*) AS n FROM cases")[0]["n"] + 1
        case_no = f"CASE-{datetime.now().year}-{count:04d}"
        execute(
            """INSERT INTO cases(case_no,title,case_type,location,incident_date,description,
               status,priority,assigned_to,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (case_no, title.strip(), case_type, location, str(inc_date), desc, "Open", priority,
             assigned, st.session_state.user["username"], datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        st.success(f"Case created: {case_no}")


def case_picker(label="Select Case"):
    cases = query("SELECT id, case_no, title FROM cases ORDER BY id DESC")
    if not cases:
        st.info("No cases available.")
        return None
    options = {f"{r['case_no']} — {r['title']}": r["id"] for r in cases}
    return options[st.selectbox(label, list(options.keys()))]


def manage_cases():
    st.header("📁 Manage Cases")
    search = st.text_input("🔍 Search by case number, title, or location")
    cases = df("SELECT * FROM cases ORDER BY id DESC")
    if search:
        mask = cases.apply(lambda r: search.lower() in f"{r['case_no']} {r['title']} {r['location']}".lower(), axis=1)
        cases = cases[mask]
    st.dataframe(
        cases[["case_no", "title", "case_type", "location", "status", "priority", "assigned_to", "created_at"]],
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("Update a Case")
    case_id = case_picker()
    if case_id is None:
        return
    case = query("SELECT * FROM cases WHERE id=?", (case_id,))[0]
    with st.form("update_case"):
        col1, col2 = st.columns(2)
        status = col1.selectbox("Status", STATUSES, index=STATUSES.index(case["status"]))
        priority = col2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(case["priority"]))
        desc = st.text_area("Description", value=case["description"] or "", height=120)
        ok = st.form_submit_button("Save Changes")
    if ok:
        execute("UPDATE cases SET status=?, priority=?, description=? WHERE id=?", (status, priority, desc, case_id))
        st.success("Case updated.")
        st.rerun()

    if is_admin():
        if st.button("🗑️ Delete This Case (Admin)"):
            for t in ("suspects", "evidence", "notes"):
                execute(f"DELETE FROM {t} WHERE case_id=?", (case_id,))
            execute("DELETE FROM cases WHERE id=?", (case_id,))
            st.warning("Case deleted.")
            st.rerun()


def suspects_page():
    st.header("👤 Suspects")
    case_id = case_picker()
    if case_id is None:
        return
    with st.form("add_suspect"):
        name = st.text_input("Name *")
        col1, col2 = st.columns(2)
        age = col1.number_input("Age", 0, 120, 25)
        status = col2.selectbox("Status", ["Person of Interest", "Suspect", "Arrested", "Cleared"])
        address = st.text_input("Address")
        desc = st.text_area("Description / Notes")
        ok = st.form_submit_button("Add Suspect")
    if ok and name.strip():
        execute("INSERT INTO suspects(case_id,name,age,address,description,status) VALUES(?,?,?,?,?,?)",
                (case_id, name.strip(), age, address, desc, status))
        st.success("Suspect added.")
        st.rerun()
    data = df("SELECT id, name, age, address, status, description FROM suspects WHERE case_id=?", (case_id,))
    st.dataframe(data, use_container_width=True, hide_index=True)


def evidence_page():
    st.header("🧾 Evidence")
    case_id = case_picker()
    if case_id is None:
        return
    with st.form("add_evidence"):
        item = st.text_input("Evidence Item *")
        desc = st.text_area("Description")
        upload = st.file_uploader("Attach file (photo, PDF, etc.)")
        ok = st.form_submit_button("Log Evidence")
    if ok and item.strip():
        path = ""
        if upload:
            safe = f"{case_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.basename(upload.name)}"
            path = os.path.join(EVIDENCE_DIR, safe)
            with open(path, "wb") as f:
                f.write(upload.getbuffer())
        execute("INSERT INTO evidence(case_id,item,description,collected_by,collected_at,file_path) VALUES(?,?,?,?,?,?)",
                (case_id, item.strip(), desc, st.session_state.user["username"],
                 datetime.now().strftime("%Y-%m-%d %H:%M"), path))
        st.success("Evidence logged.")
        st.rerun()
    rows = query("SELECT * FROM evidence WHERE case_id=? ORDER BY id DESC", (case_id,))
    for r in rows:
        with st.expander(f"{r['item']} — {r['collected_at']} by {r['collected_by']}"):
            st.write(r["description"])
            if r["file_path"] and os.path.exists(r["file_path"]):
                with open(r["file_path"], "rb") as f:
                    st.download_button("Download attachment", f, file_name=os.path.basename(r["file_path"]),
                                       key=f"dl{r['id']}")


def notes_page():
    st.header("📝 Investigation Log")
    case_id = case_picker()
    if case_id is None:
        return
    with st.form("add_note"):
        note = st.text_area("New log entry")
        ok = st.form_submit_button("Add Entry")
    if ok and note.strip():
        execute("INSERT INTO notes(case_id,author,note,created_at) VALUES(?,?,?,?)",
                (case_id, st.session_state.user["username"], note.strip(),
                 datetime.now().strftime("%Y-%m-%d %H:%M")))
        st.rerun()
    for r in query("SELECT * FROM notes WHERE case_id=? ORDER BY id DESC", (case_id,)):
        st.markdown(f"**{r['author']}** · _{r['created_at']}_")
        st.write(r["note"])
        st.divider()


def reports_page():
    st.header("📄 Reports")
    case_id = case_picker()
    if case_id is None:
        return
    case = query("SELECT * FROM cases WHERE id=?", (case_id,))[0]
    suspects = query("SELECT * FROM suspects WHERE case_id=?", (case_id,))
    evidence = query("SELECT * FROM evidence WHERE case_id=?", (case_id,))
    notes = query("SELECT * FROM notes WHERE case_id=? ORDER BY id", (case_id,))

    lines = [
        f"CASE REPORT: {case['case_no']}", "=" * 50,
        f"Title: {case['title']}", f"Type: {case['case_type']}", f"Location: {case['location']}",
        f"Incident Date: {case['incident_date']}", f"Status: {case['status']}",
        f"Priority: {case['priority']}", f"Assigned To: {case['assigned_to']}", "",
        "DESCRIPTION", case["description"] or "-", "", "SUSPECTS",
    ]
    lines += [f"- {s['name']} (age {s['age']}) [{s['status']}] {s['address'] or ''}" for s in suspects] or ["- None"]
    lines += ["", "EVIDENCE"]
    lines += [f"- {e['item']} ({e['collected_at']}, {e['collected_by']}): {e['description']}" for e in evidence] or ["- None"]
    lines += ["", "INVESTIGATION LOG"]
    lines += [f"[{n['created_at']}] {n['author']}: {n['note']}" for n in notes] or ["- None"]
    report = "\n".join(lines)
    st.text_area("Preview", report, height=350)
    st.download_button("⬇️ Download Report (.txt)", report, file_name=f"{case['case_no']}_report.txt")


def users_page():
    st.header("👮 User Management (Admin)")
    if not is_admin():
        st.error("Admins only.")
        return
    with st.form("add_user"):
        username = st.text_input("Username")
        full_name = st.text_input("Full Name")
        role = st.selectbox("Role", ["Investigator", "Admin"])
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Create User")
    if ok:
        if not username.strip() or len(password) < 6:
            st.error("Username required and password must be at least 6 characters.")
        else:
            try:
                salt = os.urandom(8).hex()
                execute("INSERT INTO users(username,full_name,role,salt,password_hash) VALUES(?,?,?,?,?)",
                        (username.strip(), full_name, role, salt, hash_pw(password, salt)))
                st.success("User created.")
            except sqlite3.IntegrityError:
                st.error("Username already exists.")
    st.dataframe(df("SELECT username, full_name, role FROM users"), use_container_width=True, hide_index=True)


def change_password():
    st.header("🔑 Change Password")
    with st.form("pw"):
        new = st.text_input("New password", type="password")
        ok = st.form_submit_button("Update")
    if ok:
        if len(new) < 6:
            st.error("Use at least 6 characters.")
        else:
            salt = os.urandom(8).hex()
            execute("UPDATE users SET salt=?, password_hash=? WHERE username=?",
                    (salt, hash_pw(new, salt), st.session_state.user["username"]))
            st.success("Password updated.")


# ---------- Main ----------
def main():
    init_db()
    if "user" not in st.session_state:
        login_page()
        return

    user = st.session_state.user
    st.sidebar.title("🕵️ CIMS")
    st.sidebar.write(f"**{user['full_name'] or user['username']}** ({user['role']})")
    pages = {
        "Dashboard": dashboard,
        "New Case": new_case,
        "Manage Cases": manage_cases,
        "Suspects": suspects_page,
        "Evidence": evidence_page,
        "Investigation Log": notes_page,
        "Reports": reports_page,
        "Change Password": change_password,
    }
    if is_admin():
        pages["User Management"] = users_page
    choice = st.sidebar.radio("Menu", list(pages.keys()))
    if st.sidebar.button("Logout"):
        del st.session_state.user
        st.rerun()
    pages[choice]()


main()
