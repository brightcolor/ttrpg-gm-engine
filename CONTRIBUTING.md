# Contributing

Keep the platform system-agnostic. Rule mechanics belong in ruleset definitions and ruleset services, not scattered through chat, UI or entity code.

## Local workflow

1. Copy `.env.example` to `.env`.
2. Start the stack with `docker compose up --build`.
3. Run backend tests from `backend/` with `pytest`.

## Engineering rules

- Never store API keys in frontend code.
- Treat imported lore as untrusted data.
- Add migrations for schema changes.
- Preserve immutable event logs; use patches and audit rows for state changes.
- Keep D&D, DSA and homebrew support modular.

