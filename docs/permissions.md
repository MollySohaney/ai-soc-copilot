# Role and permission matrix

Authorization is enforced by the central matrix in
`backend/security/rbac.py`, FastAPI permission dependencies, and permission
checks inside privileged services. Streamlit uses the same matrix only to hide
unavailable actions; UI visibility is not a security boundary.

| Capability | Viewer | Analyst | Detection Engineer | Admin |
| --- | --- | --- | --- | --- |
| Read dashboard, events, alerts, cases, activities, detection rules/runs, and existing AI results | Yes | Yes | Yes | Yes |
| Mutate alerts/cases, links, and analyst activities | No | Yes | No | Yes |
| Request alert AI triage, case Q&A, or report generation | No | Yes | No | Yes |
| Validate, test, create, update, or execute detection rules | No | No | Yes | Yes |
| Test/sync integrations or view integration operational details | No | No | No | Yes |
| Manage users, roles, activation, and sessions | No | No | No | Yes |
| Read audit events (introduced in Phase 6 Step 4) | No | No | No | Yes |

Unauthenticated requests receive `401 Authentication required.` before resource
lookup. Authenticated users without the declared permission receive
`403 Insufficient permission.` before resource lookup. Role changes and user
disablement revoke the target user's live sessions, and the final active Admin
cannot be demoted or disabled.
