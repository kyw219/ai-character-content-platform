# Security and Privacy

## Repository controls

- No `.env` files, tokens, account identifiers, deployment IDs, private URLs, logs, model weights, training data, or generated media are committed.
- Example configuration uses placeholders only.
- The CI workflow runs tests and scans tracked text for common credential formats.

## Runtime controls

- API access uses constant-time key comparison.
- OAuth token bundles are encrypted with AES-256-GCM before database storage.
- Audit events store prompt and workflow hashes rather than raw prompts.
- The publishing worker uses atomic claims and phase-aware recovery to reduce duplicate posts.
- ComfyUI is expected to run behind a private network boundary.

## Content boundary

The platform is designed for fictional synthetic characters. It rejects requests involving minors, real-person impersonation, public figures, deepfakes, and face swaps. Automated filtering is not a substitute for human review or platform-specific policy enforcement.
