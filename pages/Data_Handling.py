from pathlib import Path
import sys

import streamlit as st

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from locivra_privacy import MAX_UPLOAD_BYTES, clear_client_session

st.title("🔐 Data Handling and Security")
st.caption("Current pilot-stage controls, responsibilities and limitations")

st.info("Locivra is a validation-stage decision-support product. It does not currently claim SOC 2, ISO 27001, PIPEDA certification, SSO, a completed third-party penetration test, or enterprise production hosting.")

st.subheader("What Locivra accepts")
st.markdown("""
- Business location identifiers, names and addresses
- Aggregate location-level incident counts and loss amounts
- Aggregate information about guards, CCTV, alarms and operating context
- Non-personal validation notes required to explain a portfolio decision

Do **not** upload employee, customer, victim, suspect or witness names; emails; phone numbers; government identifiers; medical information; payment data; licence plates; detailed incident narratives; photographs; video; credentials; access codes; or other personal information.
""")

st.subheader("Current technical behaviour")
st.markdown(f"""
- Uploaded CSVs are parsed in the active Streamlit process and are not intentionally written to application storage.
- Pilot results are retained in the active browser/server session until cleared, the session expires or the process restarts.
- Reports and CSVs are created in memory and saved only when an authorized user downloads them.
- Uploads are limited to **{MAX_UPLOAD_BYTES // (1024 * 1024)} MB** and screened for unexpected columns and common personal-information patterns.
- Downloaded CSV text is escaped to reduce spreadsheet-formula injection risk.
- Secrets and generated client outputs are excluded from the public source repository.
""")

st.subheader("Pilot operating rules")
st.markdown("""
1. Obtain the client's authorization before loading location-level internal information.
2. Collect the minimum aggregate data required for the agreed pilot question.
3. Use a client code or location ID instead of personal names.
4. Store downloaded client files only in a client-approved restricted folder.
5. Do not email unencrypted working files unless the client explicitly approves that channel.
6. Keep pilot working files for the agreed engagement period, then delete or return them. Default working-file target: **30 days after pilot closeout**, unless the agreement requires another period.
7. Record deletion in the pilot closeout log. Public datasets, anonymized methodology tests and non-client code may be retained separately.
8. If client data may have been exposed, stop processing, preserve relevant logs, notify the client contact promptly and document containment and deletion actions.
""")

st.subheader("Clear this session")
st.warning("This clears Locivra results and uploaded client-derived values from the current Streamlit session. It does not delete files you already downloaded to your computer.")
confirm = st.checkbox("I understand that current Locivra session results will be cleared.")
if st.button("Clear client data from this session", disabled=not confirm, type="primary"):
    removed = clear_client_session(st.session_state)
    st.success(f"Cleared {len(removed)} Locivra session item(s).")

st.subheader("Enterprise questions to answer before a hosted deployment")
st.markdown("""
- Who will host and administer the environment?
- Where will client data be stored and backed up?
- What encryption, authentication, logging and access-review controls are required?
- What are the agreed retention, deletion, breach-notification and subcontractor terms?
- Is a privacy impact assessment, legal review, penetration test or formal certification required?

Those decisions must be agreed before Locivra represents itself as an enterprise hosted service.
""")
