# 2026-10-05 - E2 - Desk role sign-in portal

## What changed

- Signed-out Clarity Desk pages now show a dedicated sign-in portal.
- When the API enables the synthetic directory, the portal lists all nine
  staff roles. Selecting one fills its issued credentials and immediately
  authenticates through the normal server endpoint.
- The server remains authoritative for credentials, roles and permissions.
  Once authenticated, the existing permission-aware navigation exposes only
  sections available to that session.
- Deployments configured with HUTCH SSO continue to use the identity provider;
  synthetic role cards are not presented unless the API enables them.

## Validation

- Console lint and TypeScript checks pass.
- Console component suite passes (19 tests), including role-card sign-in.
- Console production build passes for all routes.

## Security boundary

The portal does not accept a requested role and does not grant permissions in
the browser. It submits credentials to the API and renders the resulting
server-issued permission set.
