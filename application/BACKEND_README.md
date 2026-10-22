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
