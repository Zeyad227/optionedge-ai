# Security Policy

## Scope

OptionEdge AI is a research and portfolio project. It is not a hosted service, and
no public deployment is operated by the maintainer.

## Reporting a Vulnerability

Please report security issues privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository. Do not open a public issue for an unpatched vulnerability.

Expect an initial response within 7 days.

## Secrets

No credentials belong in this repository. All provider keys are read from
environment variables defined in `.env`, which is git-ignored. `.env.example`
contains placeholder values only.

If you believe a credential was committed, open a private report rather than a
public issue so the key can be revoked first.

## Deploying This Project

The defaults in this repository target local development. Before exposing an
instance to a network:

- Set `API_KEY` to a long random value. Without it, every API route is public.
- Set `CORS_ORIGINS` to your exact frontend origin. Never use `*`, because
  `allow_credentials` is enabled.
- Replace the `docker-compose.yml` Postgres password (`POSTGRES_PASSWORD`) and do
  not publish the Postgres or Redis ports beyond loopback.
- Terminate TLS at a reverse proxy and add a `Content-Security-Policy` header.
- The in-process rate limiter counts by socket address. Behind a proxy, enforce
  rate limits at the proxy instead, or the whole internet shares one bucket.
- `/docs`, `/redoc`, and `/openapi.json` are unauthenticated by design for local
  use. Disable or protect them in a hostile environment.
