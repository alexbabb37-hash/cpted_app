# Locivra Data Handling and Security — Pilot Stage

**Owner:** Alex Babb / Locivra
**Applies to:** Locivra pilot engagements and locally run demonstrations
**Review trigger:** Before each client pilot, after a material architecture change, or after a security/privacy incident

## 1. Current maturity statement

Locivra is a validation-stage, founder-led decision-support product. Locivra does
not currently claim SOC 2, ISO 27001, PIPEDA certification, SSO, a completed
third-party penetration test, or enterprise production-hosting controls. This
document describes current operating rules and technical safeguards; it is not a
legal opinion or certification.

## 2. Permitted data

Locivra may process business-location identifiers, names and addresses; aggregate
location-level incident counts and loss amounts; aggregate control information;
and non-personal validation notes needed for the agreed pilot decision.

Do not provide names or direct identifiers for employees, customers, victims,
suspects or witnesses; contact information; government identifiers; health or
payment data; licence plates; detailed incident narratives; photographs or video;
credentials, access codes or security-system secrets; or unrelated personal data.

## 3. Purpose limitation and minimization

Before receiving client data, document the pilot question, authorized client
contact, permitted fields, users, retention period and approved transfer/storage
channel. Collect only fields required for the agreed analysis. Use client-defined
location IDs where possible. Internal evidence remains separate from the public-
data exposure score and is used for validation, not to manufacture a preferred
ranking.

## 4. Current application behaviour

Uploaded CSVs are parsed within the active Streamlit process and are not
intentionally written to application storage. Results can remain in active
Streamlit session state until the user clears the session, it expires or the
process restarts. Generated reports and CSVs are built in memory and saved only
when an authorized user downloads them. Uploaded files are size-limited and
screened for unexpected columns and common personal-information patterns. CSV
exports escape formula-like text.

## 5. Access, transfer and storage

- Limit client working files to Alex and specifically authorized client users.
- Keep downloaded client files in a client-approved restricted folder.
- Do not place client data, reports or credentials in the public GitHub repository.
- Do not use personal email or consumer file-sharing for sensitive working files
  unless the client explicitly approves the channel and protection.
- Lock the workstation and use current operating-system security updates.
- Do not reuse client data for another client, marketing example or product demo.

## 6. Retention and deletion

Agree on retention at pilot kickoff. Unless otherwise required, delete or return
client-supplied working files and client-identifiable outputs within 30 days after
pilot closeout. Record the date, scope and person completing deletion. Public
datasets, anonymized aggregate learnings, methodology tests and source code may be
retained separately when they contain no client confidential or personal data.

## 7. Incident response

If client data may have been accessed, disclosed, lost or altered without
authorization: stop affected processing; preserve relevant evidence; contain the
exposure; notify the authorized client contact promptly; identify affected data,
systems and time period; document recovery/deletion; and complete a written
post-incident review. Legal notification duties must be assessed with qualified
advice and the client.

## 8. Hosted-deployment gate

Before offering a hosted enterprise service, agree on architecture and ownership
for encryption in transit/at rest, authentication and least privilege, logging,
backups, vulnerability management, dependency updates, privacy review,
penetration testing, service continuity, breach notification, subcontractors,
data location, retention/deletion and contractual security commitments.
