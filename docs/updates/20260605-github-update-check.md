# Update 2026-06-05

## Summary

Added startup-time GitHub update detection for ModelPilot Gateway.

## Changes

- Added `app/update_checker.py`.
- Windows and Linux startup scripts now check GitHub before installing dependencies and starting the service.
- Added `github` configuration in `config.json` and `config.example.json`.
- Preserved local `modelpilot-gateway/config.json` during auto update.
- Documented deployment, configuration, and GitHub update settings.

## Notes

- Public repositories can pull updates without a GitHub token.
- Private repositories can set `github.token` in `config.json`.
- Auto update only fast-forwards from the configured remote branch.
