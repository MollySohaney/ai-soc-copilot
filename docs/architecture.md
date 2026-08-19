# Architecture Overview

AI SOC Copilot is structured to keep the Streamlit user interface isolated from backend logic so future security-sensitive features can be introduced with minimal coupling.

## Layers

- `app/`: Page rendering and shared UI components only.
- `backend/models/`: Typed data contracts passed between services and the UI.
- `backend/security/`: Validation and security-focused controls.
- `backend/parsers/`: File parsing and normalization helpers.
- `backend/services/`: Business workflows and orchestration.
- `backend/utils/`: Cross-cutting utilities such as logging.
- `config/`: Centralized runtime configuration.

## Design Principles

- UI should never contain parsing or validation logic.
- Services should compose validators and parsers rather than duplicating their behavior.
- Configuration should load once at startup and be injected into services.
- Logs should remain structured so later ingestion into observability tooling is straightforward.
- Security-sensitive capabilities such as AI access, secrets handling, and external lookups should be added behind dedicated service boundaries.
