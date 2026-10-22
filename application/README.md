# Cloud File Manager - Complete Package

This package contains the Node.js frontend and three backend deployment variants.

## Backend variants
- `backends/simple/` — DB credentials remain `DB_USER` and `DB_PASSWORD` environment variables.
- `backends/secrets-manager/` — DB credentials remain in AWS Secrets Manager, selected with `DB_SECRET_NAME`.
- `backends/csi/` — DB credentials remain in `/mnt/secrets/db-secret`, supplied by Secrets Store CSI Driver.

The application APIs are consistent across all three variants:
- `POST /api/upload`
- `GET /api/files`
- `GET /api/download/<s3_key>`
- `DELETE /api/delete/<s3_key>`
- `GET /api/db-test`

Delete removes the S3 object and then removes the matching row from the RDS `files` table.

## Frontend
The Node.js frontend proxies `/api/*` to the backend using `BACKEND_URL` and provides upload, list, download and delete controls.

## Important
The DB credential mechanisms were intentionally preserved. Set the required environment variables/mounts for the backend variant you deploy.
