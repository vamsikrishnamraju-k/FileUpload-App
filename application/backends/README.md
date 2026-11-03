# File Upload Backend - 3 Deployment Variants

All variants implement the same application API and S3/RDS file-manager behavior. The **only intended difference** is how each backend obtains the PostgreSQL credentials.

## Credential source by backend

- `simple`: reads `DB_USER` and `DB_PASSWORD` from environment variables.
- `secrets-manager`: reads `DB_SECRET_NAME`, calls AWS Secrets Manager using `boto3` `GetSecretValue`, and parses the returned JSON `SecretString` for `username`/`password` (or `DB_USER`/`DB_PASSWORD`). The pod's AWS workload identity must be allowed to call `secretsmanager:GetSecretValue` and, if applicable, `kms:Decrypt`.
- `csi`: reads JSON from `/mnt/secrets/db-secret` (override with `DB_SECRET_FILE`). The Secrets Store CSI Driver and AWS provider mount the secret. This Python backend does **not** call Secrets Manager to retrieve DB credentials.

## Shared API

- `GET /` — service information
- `GET /health/startup` — startup probe
- `GET /health/live` — liveness probe, independent of RDS
- `GET /health/ready` — readiness probe, checks RDS
- `GET /api/db-test` — database connectivity test
- `POST /api/upload` — multipart upload; fields: repeated `file` and optional `folderName`
- `GET /api/files` — list file metadata
- `GET /api/download/<s3_key>` — generate a 48-hour presigned download URL
- `DELETE /api/delete/<s3_key>` — delete S3 object and its RDS metadata row

Legacy aliases `/upload` and `/files` are retained for compatibility. The React frontend uses the `/api/...` routes.

## Database

The backend creates the `files` table at startup if it does not already exist. RDS must be reachable during startup. The table columns are `id`, `upload_id`, `folder_name`, `file_name`, `s3_key`, and `uploaded_at`.

## File restrictions

Only PDF and ZIP files are accepted. Each file is limited to 200 MB. S3 objects are stored in the configured private bucket; downloads are provided using presigned URLs.
