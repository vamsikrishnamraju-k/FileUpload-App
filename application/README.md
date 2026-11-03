# Cloud File Manager - Complete Package

This package contains the React frontend and three backend variants. All variants provide the same upload/list/download/delete functionality; only the DB credential retrieval method differs.

## Backend variants

- `backends/simple/`: reads `DB_USER` and `DB_PASSWORD` from environment variables.
- `backends/secrets-manager/`: uses Python `boto3` to call Secrets Manager `GetSecretValue` using `DB_SECRET_NAME`.
- `backends/csi/`: reads the JSON secret mounted at `/mnt/secrets/db-secret` by Secrets Store CSI Driver. This backend does not use boto3 to retrieve DB credentials.

## API routes

- `POST /api/upload`
- `GET /api/files`
- `GET /api/download/<s3_key>`
- `DELETE /api/delete/<s3_key>`
- `GET /api/db-test`
- `GET /health/startup`, `/health/live`, `/health/ready`

Uploads accept PDF and ZIP files up to 200 MB each. Download links expire after 48 hours. Delete removes the S3 object and matching RDS metadata row.

## Frontend

The Node.js frontend proxies `/api/*` requests to the backend using `BACKEND_URL`. The React interface supports upload, list, download, and delete.

## Kubernetes

See `k8s/deployment-secrets-manager.yaml` for the direct boto3 variant and `k8s/deployment-csi.yaml` plus `k8s/secretproviderclass-csi.yaml` for the CSI-mounted variant. Replace the documented placeholders and ensure the required AWS workload identity permissions are configured before applying.
