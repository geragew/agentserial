# Security policy

## Supported versions

Security fixes are applied to the latest AgentSerial release.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Send a concise report
to `GERAGEW@ICLOUD.COM` with the affected version, reproduction steps, impact,
and any suggested mitigation. Do not include real customer traces or secrets.

## API deployment boundary

The API defaults to `127.0.0.1` and has no key unless one is configured. Before
binding to a public or shared interface:

1. Set a strong `AGENTSERIAL_API_KEY` and pass it as `X-AgentSerial-Key`.
2. Terminate TLS at a trusted reverse proxy or API gateway.
3. Set explicit `AGENTSERIAL_CORS_ORIGINS` values.
4. Keep body, operation, prefix, timeout, and rate limits enabled.
5. Run the container as its non-root user with a read-only filesystem.
6. Avoid uploading histories containing prompts, credentials, or personal data.

The built-in rate limiter is per process. Multi-instance deployments should
enforce a shared limit at the gateway or through a shared data store.
