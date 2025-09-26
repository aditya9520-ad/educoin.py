"""
educoin_streamlit_app.py
Streamlit Classroom Cryptocurrency (EduCoin)

Run:
    pip install streamlit
    pip install -r requirements.txt    # or `pip install streamlit` if you don't use requirements file
    export TEACHER_PASSWORD=yourpass   # Windows CMD: set TEACHER_PASSWORD=yourpass
    streamlit run educoin_streamlit_app.py
"""

import streamlit as st
import sqlite3
import os
import uuid
import datetime

# CONFIG
DB_PATH = os.path.join(os.path.dirname(__file__), "educoin.db")
TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", "teacherpass")  # override in env for production

# -------------------------
# Database helpers
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            public_address TEXT NOT NULL UNIQUE,
            pin TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            from_addr TEXT,
            to_addr TEXT,
            amount INTEGER NOT NULL,
            note TEXT
        );
        """
    )
    conn.commit()
    conn.close()

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def create_user(name: str):
    conn = get_db_connection()
    uid = str(uuid.uuid4())
    addr = "EDU-" + uid[:8]
    pin = str(uuid.uuid4())[:6]  # 6-char PIN for a bit more usability
    created_at = now_iso()
    conn.execute(
        "INSERT INTO users (id, name, public_address, pin, balance, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, name, addr, pin, 0, created_at),
    )
    conn.commit()
    conn.close()
    return {"id": uid, "name": name, "public_address": addr, "pin": pin, "balance": 0, "created_at": created_at}

def get_user_by_addr(addr: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE public_address = ?", (addr,)).fetchone()
    conn.close()
    return row

def update_balance(addr: str, new_balance: int):
    conn = get_db_connection()
    conn.execute("UPDATE users SET balance = ? WHERE public_address = ?", (new_balance, addr))
    conn.commit()
    conn.close()

def add_transaction(from_addr, to_addr, amount: int, note: str = None):
    tid = str(uuid.uuid4())
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO transactions (id, timestamp, from_addr, to_addr, amount, note) VALUES (?, ?, ?, ?, ?, ?)",
        (tid, now_iso(), from_addr, to_addr, amount, note),
    )
    conn.commit()
    conn.close()
    return tid

def get_all_users():
    conn = get_db_connection()
    rows = conn.execute("SELECT name, public_address, balance FROM users ORDER BY balance DESC").fetchall()
    conn.close()
    return rows

def get_ledger(limit=200):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT timestamp, from_addr, to_addr, amount, note FROM transactions ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows

# Initialize DB on import
init_db()

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="EduCoin Classroom", layout="wide")
st.title("🎓 EduCoin — Classroom Cryptocurrency")
st.markdown(
    "A simple classroom economy: teacher mints coins, students transfer them, and everyone sees balances & a leaderboard."
)

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Create Wallet", "Mint (Teacher)", "Transfer"])

# DASHBOARD
if menu == "Dashboard":
    st.header("Balances & Leaderboard")
    users = get_all_users()
    if users:
        st.table([{"Name": u["name"], "Address": u["public_address"], "Balance": u["balance"]} for u in users])
    else:
        st.info("No users found. Create wallets from the 'Create Wallet' page.")

    st.subheader("Recent Transactions (Ledger)")
    ledger = get_ledger(50)
    if ledger:
        st.table(
            [
                {
                    "Time": t["timestamp"],
                    "From": (t["from_addr"] or "MINT"),
                    "To": t["to_addr"],
                    "Amount": t["amount"],
                    "Note": t["note"] or "",
                }
                for t in ledger
            ]
        )
    else:
        st.info("No transactions yet.")

# CREATE WALLET
elif menu == "Create Wallet":
    st.header("Create a Student Wallet")
    name = st.text_input("Student name")
    if st.button("Create Wallet"):
        if not name.strip():
            st.error("Name is required.")
        else:
            user = create_user(name.strip())
            st.success("Wallet created!")
            st.code(f"Address: {user['public_address']}\nPIN: {user['pin']}", language="text")
            st.info("Copy the address and PIN and give them to the student. Keep PIN secret for transfers.")

# MINT (teacher-only)
elif menu == "Mint (Teacher)":
    st.header("Teacher Minting (Create EduCoins)")
    col1, col2 = st.columns([2, 1])
    with col1:
        to_addr = st.text_input("Recipient address (e.g. EDU-xxxxxxxx)")
        amount = st.number_input("Amount to mint", min_value=1, value=1, step=1)
        note = st.text_input("Note", value="minted by teacher")
    with col2:
        password = st.text_input("Teacher password", type="password")
        st.write("")
        if st.button("Mint"):
            if password != TEACHER_PASSWORD:
                st.error("Invalid teacher password.")
            elif not to_addr:
                st.error("Recipient address required.")
            else:
                user = get_user_by_addr(to_addr)
                if not user:
                    st.error("Recipient not found.")
                else:
                    new_balance = user["balance"] + int(amount)
                    update_balance(to_addr, new_balance)
                    tid = add_transaction(None, to_addr, int(amount), note)
                    st.success(f"Minted {amount} EduCoin(s) to {to_addr}.")
                    st.write(f"Transaction id: {tid}")
                    st.write(f"New balance: {new_balance}")

# TRANSFER
elif menu == "Transfer":
    st.header("Transfer EduCoins (Student)")
    from_addr = st.text_input("Sender address")
    pin = st.text_input("Sender PIN", type="password")
    to_addr = st.text_input("Recipient address")
    amount = st.number_input("Amount to transfer", min_value=1, value=1, step=1)
    note = st.text_input("Note (optional)")
    if st.button("Transfer"):
        if not all([from_addr, to_addr]):
            st.error("Both sender and recipient addresses are required.")
        else:
            sender = get_user_by_addr(from_addr)
            receiver = get_user_by_addr(to_addr)
            if not sender:
                st.error("Sender not found.")
            elif not receiver:
                st.error("Recipient not found.")
            elif pin != sender["pin"]:
                st.error("Invalid PIN.")
            elif sender["balance"] < amount:
                st.error("Insufficient balance.")
            else:
                update_balance(from_addr, sender["balance"] - int(amount))
                update_balance(to_addr, receiver["balance"] + int(amount))
                tid = add_transaction(from_addr, to_addr, int(amount), note)
                st.success(f"Transferred {amount} EduCoin(s) from {from_addr} to {to_addr}.")
                st.write(f"Transaction id: {tid}")

# Footer / quick tips
st.sidebar.markdown("---")
st.sidebar.markdown("**Quick tips**")
st.sidebar.markdown("- Teacher mints coins with the teacher password.\n- Students need their Address + PIN to transfer.\n- Database file: `educoin.db` in the same folder.")
