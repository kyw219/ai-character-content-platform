# Architecture

## Generation service

The FastAPI service owns authentication, policy validation, workflow construction, ComfyUI submission, job lookup, and privacy-preserving audit events. The API edits a copy of the workflow template for every request so concurrent jobs cannot mutate shared state.

## Quality loop

A multimodal reviewer evaluates each candidate for prompt adherence, identity stability, and visible artifacts. The orchestration contract has three outcomes:

- `accept` moves the candidate into human review or scheduling.
- `revise` returns a targeted prompt and resubmits it, up to three revisions.
- `manual_review` stops automatic retries when the reviewer cannot provide a safe revision or the revision limit is reached.

The public repository keeps the reviewer provider-neutral because production prompts, assets, and vendor credentials are private.

## Publishing worker

The Cloudflare Worker stores scheduling state in D1. A conditional update from `PLANNED` to `POSTING` acts as an atomic claim, preventing two cron invocations from publishing the same item.

Publishing records progress by phase:

1. `prepare` validates state and gathers media.
2. `create` sends the irreversible platform request.
3. `POSTED` records the returned platform identifier.

Failures before `create` can return to `PLANNED` with a backoff timestamp. Failures during or after `create` move to `PUBLISH_REVIEW`, because automatically retrying an uncertain create request could duplicate a post. Stale jobs follow the same phase-aware recovery rule.

## Deployment boundary

ComfyUI and model files remain on a private GPU network. The public API should never expose the ComfyUI port directly. Production deployments should use a secret manager, short-lived media URLs, rate limits, per-tenant quotas, human review, provenance metadata, and deletion/reporting workflows.
