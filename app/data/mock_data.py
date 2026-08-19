"""Purpose: Centralized realistic mock/demo data for the AI SOC Copilot UI prototype.

Nothing in this module talks to a real SIEM, AI provider, or threat-intel API.
All values are illustrative and intended to be replaced by live services later.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_METRICS = [
    {"label": "Active Alerts", "value": "24", "delta": "+6 in the last 24h", "tone": "neutral"},
    {"label": "Critical Alerts", "value": "4", "delta": "2 require immediate review", "tone": "critical"},
    {"label": "Open Investigations", "value": "7", "delta": "3 assigned today", "tone": "neutral"},
    {"label": "IOCs Detected", "value": "38", "delta": "12 unique sources", "tone": "neutral"},
]

ALERT_ACTIVITY_SERIES = {
    "days": ["Aug 9", "Aug 10", "Aug 11", "Aug 12", "Aug 13", "Aug 14", "Aug 15"],
    "Critical": [1, 2, 1, 3, 2, 4, 4],
    "High": [4, 5, 6, 5, 7, 8, 8],
    "Medium": [10, 12, 11, 14, 15, 17, 19],
    "Low": [6, 7, 8, 7, 9, 10, 12],
}

SEVERITY_DISTRIBUTION = [
    {"severity": "Critical", "count": 4},
    {"severity": "High", "count": 8},
    {"severity": "Medium", "count": 19},
    {"severity": "Low", "count": 12},
]

RECENT_ALERTS = [
    {
        "severity": "Critical",
        "alert": "Potential Credential Dumping",
        "source": "CrowdStrike",
        "source_ip": "10.20.4.17",
        "user": "svc_backup",
        "timestamp": "2026-08-15 09:41",
        "status": "New",
    },
    {
        "severity": "High",
        "alert": "Multiple Failed SSH Logins",
        "source": "Wazuh",
        "source_ip": "185.220.101.42",
        "user": "admin",
        "timestamp": "2026-08-15 09:22",
        "status": "Investigating",
    },
    {
        "severity": "High",
        "alert": "Suspicious PowerShell Execution",
        "source": "Microsoft Defender",
        "source_ip": "10.20.6.31",
        "user": "j.alvarez",
        "timestamp": "2026-08-15 08:57",
        "status": "Investigating",
    },
    {
        "severity": "Medium",
        "alert": "New Scheduled Task Created",
        "source": "Sentinel",
        "source_ip": "10.20.6.31",
        "user": "j.alvarez",
        "timestamp": "2026-08-15 08:59",
        "status": "New",
    },
    {
        "severity": "Medium",
        "alert": "Impossible Travel Login",
        "source": "Elastic",
        "source_ip": "41.203.72.18",
        "user": "r.chen",
        "timestamp": "2026-08-15 07:12",
        "status": "Contained",
    },
    {
        "severity": "Low",
        "alert": "Unusual Outbound Network Connection",
        "source": "Zeek",
        "source_ip": "10.20.9.5",
        "user": "prod-web-03",
        "timestamp": "2026-08-15 06:48",
        "status": "Resolved",
    },
]

MITRE_ACTIVITY = [
    {"technique_id": "T1110", "name": "Brute Force", "count": 14},
    {"technique_id": "T1059.001", "name": "PowerShell", "count": 9},
    {"technique_id": "T1053.005", "name": "Scheduled Task", "count": 6},
    {"technique_id": "T1078", "name": "Valid Accounts", "count": 5},
]


# ---------------------------------------------------------------------------
# Analyze Alert
# ---------------------------------------------------------------------------

SAMPLE_ALERT_JSON = """{
  "event_type": "authentication_failure",
  "source_ip": "185.220.101.42",
  "destination_ip": "10.0.0.24",
  "username": "admin",
  "failed_attempts": 18,
  "protocol": "SSH",
  "destination_port": 22,
  "platform": "wazuh",
  "host": "prod-bastion-01"
}"""

PLATFORM_OPTIONS = [
    "Auto Detect",
    "Elastic",
    "Splunk",
    "Microsoft Sentinel",
    "Wazuh",
    "CrowdStrike",
    "Microsoft Defender",
    "Generic JSON",
]

ANALYSIS_RESULT = {
    "summary": (
        "Repeated SSH authentication failures from 185.220.101.42 targeting the admin account "
        "indicate a likely credential brute-force attempt. Eighteen failed authentication events "
        "occurred within a short period, followed by no successful login on this host."
    ),
    "severity": "High",
    "confidence": 94,
    "category": "Credential Access",
    "risk_score": 82,
    "risk_label": "HIGH RISK",
    "risk_factors": [
        "High authentication failure volume",
        "Privileged account targeted",
        "Single source IP",
        "Attempts occurred within a short time window",
    ],
    "mitre": {
        "tactic": "Credential Access",
        "technique_id": "T1110",
        "technique": "Brute Force",
        "sub_technique_id": "T1110.001",
        "sub_technique": "Password Guessing",
    },
    "iocs": [
        {"type": "IP Address", "value": "185.220.101.42"},
        {"type": "User", "value": "admin"},
        {"type": "Destination", "value": "10.0.0.24"},
        {"type": "Port", "value": "22"},
    ],
    "checklist": [
        "Search for successful authentication from the source IP",
        "Review authentication activity for the targeted account",
        "Determine whether the source IP belongs to an approved scanner",
        "Check for privilege escalation following authentication",
        "Search for persistence activity",
        "Review other systems contacted by the source host",
    ],
    "false_positives": [
        "Vulnerability scanner",
        "Internal penetration testing",
        "Misconfigured automation",
        "User repeatedly entering an incorrect password",
    ],
    "response": {
        "Immediate Actions": [
            "Validate whether the source is authorized",
            "Temporarily block the source if malicious",
            "Review the targeted account",
        ],
        "Containment": [
            "Disable compromised accounts if necessary",
            "Terminate suspicious active sessions",
        ],
        "Remediation": [
            "Enforce MFA",
            "Review account lockout policy",
            "Rotate exposed credentials",
        ],
    },
}


# ---------------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------------

INVESTIGATION_METRICS = [
    {"label": "Open", "value": "7"},
    {"label": "Critical", "value": "2"},
    {"label": "Under Review", "value": "4"},
    {"label": "Resolved This Week", "value": "13"},
]

INVESTIGATIONS = [
    {
        "id": "INC-2026-0042",
        "title": "SSH Brute Force Followed by Successful Login",
        "severity": "High",
        "status": "Investigating",
        "assignee": "Molly S.",
        "alerts": 14,
        "created": "Aug 15, 2026",
        "updated": "5 min ago",
        "source": "Wazuh",
        "host": "prod-bastion-01",
        "user": "admin",
    },
    {
        "id": "INC-2026-0041",
        "title": "Suspicious PowerShell Activity",
        "severity": "High",
        "status": "New",
        "assignee": "D. Okafor",
        "alerts": 6,
        "created": "Aug 15, 2026",
        "updated": "38 min ago",
        "source": "Microsoft Defender",
        "host": "fin-ws-014",
        "user": "j.alvarez",
    },
    {
        "id": "INC-2026-0039",
        "title": "Potential Credential Dumping",
        "severity": "Critical",
        "status": "Investigating",
        "assignee": "Molly S.",
        "alerts": 9,
        "created": "Aug 14, 2026",
        "updated": "1 hr ago",
        "source": "CrowdStrike",
        "host": "dc-primary-02",
        "user": "svc_backup",
    },
    {
        "id": "INC-2026-0037",
        "title": "Unusual Administrative Login",
        "severity": "Medium",
        "status": "Contained",
        "assignee": "R. Chen",
        "alerts": 3,
        "created": "Aug 13, 2026",
        "updated": "6 hrs ago",
        "source": "Sentinel",
        "host": "corp-vpn-gw",
        "user": "r.chen",
    },
    {
        "id": "INC-2026-0035",
        "title": "Possible Persistence via Scheduled Task",
        "severity": "Medium",
        "status": "Resolved",
        "assignee": "D. Okafor",
        "alerts": 4,
        "created": "Aug 12, 2026",
        "updated": "1 day ago",
        "source": "Sentinel",
        "host": "fin-ws-014",
        "user": "j.alvarez",
    },
    {
        "id": "INC-2026-0031",
        "title": "Impossible Travel Login on Finance Account",
        "severity": "Low",
        "status": "Resolved",
        "assignee": "Molly S.",
        "alerts": 2,
        "created": "Aug 10, 2026",
        "updated": "3 days ago",
        "source": "Elastic",
        "host": "n/a",
        "user": "r.chen",
    },
]

INVESTIGATION_TIMELINE = [
    {"time": "10:14", "event": "Failed SSH Login", "detail": "admin@prod-bastion-01 from 185.220.101.42"},
    {"time": "10:14", "event": "Failed SSH Login", "detail": "admin@prod-bastion-01 from 185.220.101.42"},
    {"time": "10:15", "event": "Successful SSH Login", "detail": "admin@prod-bastion-01 from 185.220.101.42"},
    {"time": "10:18", "event": "sudo Command Executed", "detail": "sudo cat /etc/shadow"},
    {"time": "10:22", "event": "Cron Job Created", "detail": "/etc/cron.d/sysupdate installed"},
]

INVESTIGATION_EVIDENCE = [
    {
        "timestamp": "2026-08-15 10:14:02",
        "event_type": "Authentication Failure",
        "source": "Wazuh",
        "evidence": "18 failed SSH attempts from 185.220.101.42",
    },
    {
        "timestamp": "2026-08-15 10:15:47",
        "event_type": "Authentication Success",
        "source": "Wazuh",
        "evidence": "Successful login as admin from 185.220.101.42",
    },
    {
        "timestamp": "2026-08-15 10:18:33",
        "event_type": "Process Execution",
        "source": "CrowdStrike",
        "evidence": "sudo cat /etc/shadow executed by admin",
    },
    {
        "timestamp": "2026-08-15 10:22:11",
        "event_type": "Persistence",
        "source": "CrowdStrike",
        "evidence": "New cron entry /etc/cron.d/sysupdate",
    },
]

INVESTIGATION_OVERVIEW = (
    "AI-assisted summary: The source IP 185.220.101.42, associated with known Tor exit node "
    "infrastructure, conducted a sustained brute-force campaign against the admin account on "
    "prod-bastion-01. Authentication ultimately succeeded, followed by privileged command execution "
    "and the creation of a persistence mechanism via cron. This pattern is consistent with external "
    "credential access leading to host compromise and warrants immediate containment."
)

INVESTIGATION_NOTES = [
    {"author": "Molly S.", "time": "09:52", "note": "Confirmed source IP is a known Tor exit node via internal watchlist."},
    {"author": "Molly S.", "time": "10:31", "note": "Escalated to containment — disabling admin account pending credential rotation."},
]


# ---------------------------------------------------------------------------
# MITRE ATT&CK
# ---------------------------------------------------------------------------

MITRE_TACTICS = [
    "Reconnaissance",
    "Resource Development",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact",
]

MITRE_TECHNIQUES = [
    {
        "id": "T1110",
        "name": "Brute Force",
        "tactics": ["Credential Access"],
        "description": (
            "Adversaries may use brute force techniques to gain access to accounts when passwords "
            "are unknown or when password hashes are obtained."
        ),
        "observed_in": 14,
        "related_investigations": 3,
        "detections": [
            "Excessive authentication failures",
            "Multiple accounts targeted from a single host",
            "Authentication success following repeated failures",
        ],
    },
    {
        "id": "T1110.001",
        "name": "Password Guessing",
        "tactics": ["Credential Access"],
        "description": "Adversaries with no prior knowledge of legitimate credentials may guess passwords to attempt access to accounts.",
        "observed_in": 8,
        "related_investigations": 2,
        "detections": [
            "High volume of failed logins against a single account",
            "Login attempts across a narrow username set",
        ],
    },
    {
        "id": "T1059.001",
        "name": "PowerShell",
        "tactics": ["Execution"],
        "description": (
            "Adversaries may abuse PowerShell commands and scripts for execution, often using "
            "encoded or obfuscated commands to evade detection."
        ),
        "observed_in": 9,
        "related_investigations": 2,
        "detections": [
            "Encoded command-line arguments",
            "PowerShell spawning from an unusual parent process",
            "Download cradles in script block logs",
        ],
    },
    {
        "id": "T1053.005",
        "name": "Scheduled Task/Job",
        "tactics": ["Persistence", "Privilege Escalation"],
        "description": "Adversaries may abuse the Windows Task Scheduler or cron to perform task scheduling for initial or recurring execution of malicious code.",
        "observed_in": 6,
        "related_investigations": 2,
        "detections": [
            "New scheduled task or cron entry creation",
            "Tasks referencing uncommon binaries or scripts",
        ],
    },
    {
        "id": "T1078",
        "name": "Valid Accounts",
        "tactics": ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access"],
        "description": "Adversaries may obtain and abuse credentials of existing accounts as a means of gaining Initial Access, Persistence, Privilege Escalation, or Defense Evasion.",
        "observed_in": 5,
        "related_investigations": 2,
        "detections": [
            "Logins from unusual geolocations",
            "Impossible travel between successive logins",
            "Off-hours administrative access",
        ],
    },
    {
        "id": "T1003",
        "name": "OS Credential Dumping",
        "tactics": ["Credential Access"],
        "description": "Adversaries may attempt to dump credentials to obtain account login and credential material, normally in the form of a hash or a clear text password.",
        "observed_in": 3,
        "related_investigations": 1,
        "detections": [
            "Access to LSASS process memory",
            "Reads of /etc/shadow or SAM registry hives",
        ],
    },
    {
        "id": "T1071",
        "name": "Application Layer Protocol",
        "tactics": ["Command and Control"],
        "description": "Adversaries may communicate using OSI application layer protocols to avoid detection by blending in with existing traffic.",
        "observed_in": 4,
        "related_investigations": 1,
        "detections": [
            "Beaconing intervals to external hosts",
            "Unusual user-agent strings in HTTP traffic",
        ],
    },
    {
        "id": "T1105",
        "name": "Ingress Tool Transfer",
        "tactics": ["Command and Control"],
        "description": "Adversaries may transfer tools or other files from an external system into a compromised environment.",
        "observed_in": 2,
        "related_investigations": 1,
        "detections": [
            "Outbound connections followed by new binary creation",
            "Unsigned executables written to temp directories",
        ],
    },
]


# ---------------------------------------------------------------------------
# Threat Intelligence
# ---------------------------------------------------------------------------

THREAT_INTEL_TYPES = ["Auto Detect", "IP Address", "Domain", "URL", "File Hash"]

THREAT_INTEL_RESULT = {
    "indicator": "185.220.101.42",
    "type": "IP Address",
    "reputation": "Malicious",
    "risk_score": 87,
    "malicious_vendors": 12,
    "suspicious_vendors": 4,
    "harmless_vendors": 38,
    "last_observed": "2 days ago",
    "country": "Netherlands",
    "asn": "AS208294 (Tor Exit Relay Operator)",
    "organization": "Tor Exit Node Infrastructure",
    "known_malware": "None associated directly; frequently used as anonymization relay for credential-stuffing tooling",
    "associated_domains": ["torproject-exit-42.example", "relay-node-nl.example"],
    "related_techniques": ["T1110 — Brute Force", "T1071 — Application Layer Protocol"],
}

THREAT_INTEL_SOURCES = [
    {"name": "VirusTotal", "status": "Mock Data"},
    {"name": "AbuseIPDB", "status": "Mock Data"},
    {"name": "AlienVault OTX", "status": "Not Connected"},
]

THREAT_INTEL_HISTORY = [
    {"indicator": "185.220.101.42", "type": "IP Address", "risk": 87, "verdict": "Malicious", "last_checked": "2 min ago"},
    {"indicator": "fin-update-cdn.net", "type": "Domain", "risk": 62, "verdict": "Suspicious", "last_checked": "1 hr ago"},
    {"indicator": "44d88612fea8a8f36de82e1278abb02f", "type": "File Hash", "risk": 95, "verdict": "Malicious", "last_checked": "3 hrs ago"},
    {"indicator": "41.203.72.18", "type": "IP Address", "risk": 21, "verdict": "Harmless", "last_checked": "1 day ago"},
    {"indicator": "hxxp://update-service[.]biz/payload.bin", "type": "URL", "risk": 91, "verdict": "Malicious", "last_checked": "2 days ago"},
]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

REPORT_METRICS = [
    {"label": "Reports Generated", "value": "24"},
    {"label": "This Month", "value": "8"},
    {"label": "Drafts", "value": "3"},
    {"label": "Completed", "value": "21"},
]

REPORTS = [
    {
        "report": "INC-2026-0042 Incident Report",
        "investigation": "SSH Brute Force Followed by Login",
        "severity": "High",
        "status": "Completed",
        "created": "Aug 15, 2026",
        "format": "PDF",
    },
    {
        "report": "INC-2026-0039 Incident Report",
        "investigation": "Potential Credential Dumping",
        "severity": "Critical",
        "status": "Completed",
        "created": "Aug 14, 2026",
        "format": "PDF",
    },
    {
        "report": "INC-2026-0041 Incident Report",
        "investigation": "Suspicious PowerShell Activity",
        "severity": "High",
        "status": "Draft",
        "created": "Aug 15, 2026",
        "format": "DOCX",
    },
    {
        "report": "INC-2026-0037 Incident Report",
        "investigation": "Unusual Administrative Login",
        "severity": "Medium",
        "status": "Completed",
        "created": "Aug 13, 2026",
        "format": "Markdown",
    },
    {
        "report": "INC-2026-0035 Incident Report",
        "investigation": "Possible Persistence via Scheduled Task",
        "severity": "Medium",
        "status": "Completed",
        "created": "Aug 12, 2026",
        "format": "PDF",
    },
]

REPORT_PREVIEW = {
    "title": "INC-2026-0042 — SSH Brute Force Followed by Successful Login",
    "executive_summary": (
        "On August 15, 2026, prod-bastion-01 was targeted by a sustained SSH brute-force campaign "
        "originating from 185.220.101.42. The attempt succeeded in authenticating as the admin "
        "account, after which the attacker executed privileged commands and established persistence "
        "via a cron job. The account has been disabled and credentials rotated as part of containment."
    ),
    "incident_overview": {
        "Severity": "High",
        "Status": "Investigating",
        "Affected Host": "prod-bastion-01",
        "Affected User": "admin",
        "Source": "Wazuh",
    },
    "timeline": INVESTIGATION_TIMELINE,
    "mitre": [
        "T1110 — Brute Force (Credential Access)",
        "T1110.001 — Password Guessing (Credential Access)",
        "T1078 — Valid Accounts (Persistence)",
    ],
    "iocs": ANALYSIS_RESULT["iocs"],
    "findings": [
        "18 failed authentication attempts preceded a successful login within a 90-second window.",
        "Source IP is a known Tor exit relay associated with prior credential-stuffing activity.",
        "Privileged command execution and cron-based persistence followed the successful login.",
    ],
    "containment_actions": [
        "Disabled the admin account on prod-bastion-01",
        "Blocked 185.220.101.42 at the perimeter firewall",
        "Removed the unauthorized cron entry",
    ],
    "recommendations": [
        "Enforce MFA for all administrative SSH access",
        "Reduce authentication failure lockout threshold",
        "Rotate credentials for all accounts with bastion access",
    ],
    "analyst_notes": (
        "Recommend a follow-up review of bastion host firewall rules to restrict SSH exposure to "
        "known management IP ranges."
    ),
}


# ---------------------------------------------------------------------------
# Integrations
# ---------------------------------------------------------------------------

SIEM_INTEGRATIONS = [
    {"name": "Elastic Security", "category": "SIEM", "status": "Available Soon"},
    {"name": "Splunk", "category": "SIEM", "status": "Available Soon"},
    {"name": "Microsoft Sentinel", "category": "SIEM", "status": "Available Soon"},
    {"name": "Wazuh", "category": "SIEM / XDR", "status": "Available Soon"},
    {"name": "Microsoft Defender", "category": "Endpoint Security", "status": "Available Soon"},
    {"name": "CrowdStrike", "category": "Endpoint Security", "status": "Available Soon"},
]

TI_INTEGRATIONS = [
    {"name": "VirusTotal", "category": "Threat Intelligence", "status": "Not Connected"},
    {"name": "AbuseIPDB", "category": "Threat Intelligence", "status": "Not Connected"},
    {"name": "AlienVault OTX", "category": "Threat Intelligence", "status": "Not Connected"},
]


# ---------------------------------------------------------------------------
# Copilot panel
# ---------------------------------------------------------------------------

COPILOT_CONVERSATION = [
    {"role": "analyst", "text": "Why is this alert suspicious?"},
    {
        "role": "copilot",
        "text": (
            "The alert contains 18 failed SSH authentication attempts against a privileged account "
            "within a short time window. This pattern is commonly associated with password guessing "
            "activity."
        ),
    },
    {"role": "analyst", "text": "Is the source IP known to be malicious?"},
    {
        "role": "copilot",
        "text": (
            "Yes — 185.220.101.42 resolves to a known Tor exit relay with prior credential-stuffing "
            "activity reported by threat intelligence sources. Treat traffic from this address as "
            "high risk."
        ),
    },
]
