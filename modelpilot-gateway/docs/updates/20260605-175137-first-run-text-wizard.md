# Update 2026-06-05 17:51

## Summary

Added a first-run terminal text wizard for ModelPilot Gateway.

## Changes

- Added `app/setup_wizard.py` with a bilingual text-based setup flow.
- Startup scripts now run `python -m app.setup_wizard` after dependency installation and before Uvicorn starts.
- Added `setup.completed`, `setup.language`, and `setup.completed_at` to default config files.
- Updated README and `config.schema.md` for the text wizard workflow.
- Added tests for setup payload merging, config writing, first-run prompt flow, and completed-setup skip behavior.

## Notes

- The wizard asks users to choose Chinese or English first.
- The wizard configures backend models, classifier, default user API key, quotas, allowed models, and auto-upgrade permission.
- Re-run with `python -m app.setup_wizard --force`.
