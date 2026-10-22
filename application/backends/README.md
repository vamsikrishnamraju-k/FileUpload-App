# File Upload Backend - 3 Deployment Variants

The application API is shared across all three variants. Only the database credential source differs.

## API
- GET /
- GET /api/db-test
- POST /api/upload (multipart: file, optional fileName)
- GET /api/files
- GET /api/download/<s3_key>
- DELETE /api/delete/<s3_key>

Delete removes the S3 object and then removes its matching RDS row.

## Credential variants
- simple: DB_USER and DB_PASSWORD environment variables
- secrets-manager: DB_SECRET_NAME environment variable; username/password read from AWS Secrets Manager
- csi: username/password read from /mnt/secrets/db-secret JSON mounted by Secrets Store CSI Driver

The frontend should call the same API routes for all three variants.


## RDS health and Kubernetes behavior

The backend treats PostgreSQL/RDS as a required dependency.

- The application performs `init_db()` during startup. If RDS is unavailable, startup fails and the container exits with a non-zero status. Kubernetes can then restart it.
- `GET /health/ready` checks RDS and returns `200` when the database is reachable, otherwise `503`. Use this as the Kubernetes readiness probe so an unhealthy pod is removed from Service traffic.
- `GET /health/live` checks RDS and returns `200` when the database is reachable, otherwise `500`. Use this as the Kubernetes liveness probe if the requirement is to restart the pod when RDS becomes unavailable.
- PostgreSQL uses `connect_timeout=5` so a dead/unreachable RDS does not leave health checks hanging for a long time.

Example probe configuration:

```yaml
startupProbe:
  httpGet:
    path: /health/ready
    port: 5000
  failureThreshold: 30
  periodSeconds: 5

readinessProbe:
  httpGet:
    path: /health/ready
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3

livenessProbe:
  httpGet:
    path: /health/live
    port: 5000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
```

With this configuration, if RDS goes down, readiness fails first and the pod stops receiving traffic. If the database remains unavailable long enough for the liveness failure threshold, Kubernetes restarts the container.
