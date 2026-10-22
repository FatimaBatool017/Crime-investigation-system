# Crime-investigation-system
# 🕵️ Crime Investigation Management System (CIMS)

A Streamlit + SQLite app for managing criminal cases, suspects, evidence, and investigation logs.

## Features
- Secure login with hashed passwords (Admin / Investigator roles)
- Dashboard with case statistics and charts
- Register, search, update, and (admin) delete cases
- Suspect tracking per case
- Evidence log with file attachments
- Investigation log (timestamped notes)
- Downloadable case reports
- Admin user management

## Run locally
1. Install Python 3.10+
2. Create a folder and place `app.py`, `requirements.txt`, `README.md` inside
3. Open a terminal in that folder:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. Open http://localhost:8501
5. Log in with `admin` / `admin123`, then change the password immediately (sidebar → Change Password)

## Deploy on Streamlit Community Cloud
1. Create a GitHub repo and upload the three files
2. Go to https://share.streamlit.io and sign in with GitHub
3. Click **New app**, choose your repo, branch `main`, main file `app.py`
4. Click **Deploy**

> Note: Streamlit Cloud storage is temporary, so the SQLite database and uploaded evidence reset when the app restarts. For real use, host on a VPS or switch to a hosted database (e.g. PostgreSQL/Supabase).

## Security notes
- Change the default admin password first
- Use this only on a private/protected deployment; case data is sensitive
- Back up `crime_system.db` and `evidence_files/` regularly
