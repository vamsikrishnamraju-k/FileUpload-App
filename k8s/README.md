# Kubernetes deployment variants

Replace all `YOUR_...` placeholders before applying. These manifests assume the `backend` namespace and an existing `file-app` ServiceAccount. Attach the appropriate AWS permissions to that workload identity for S3 access and, where applicable, Secrets Manager access.

## Secrets Manager backend

Build and push the image from `cloud-file-manager-complete-v1/backends/secrets-manager/`, then apply:

```bash
kubectl apply -f deployment-secrets-manager.yaml
```

The Python backend uses `boto3` `secretsmanager:GetSecretValue` with `DB_SECRET_NAME`. The secret's SecretString must be JSON containing `username` and `password` (or `DB_USER` and `DB_PASSWORD`). The workload identity needs `secretsmanager:GetSecretValue`; add `kms:Decrypt` if the secret uses a customer-managed KMS key. It also needs the required S3 permissions.

## CSI backend

First install the Secrets Store CSI Driver and AWS provider. Create/update `secretproviderclass-csi.yaml` with the real secret name, then apply both resources:

```bash
kubectl apply -f secretproviderclass-csi.yaml
kubectl apply -f deployment-csi.yaml
```

The CSI driver mounts the Secrets Manager SecretString as `/mnt/secrets/db-secret`. The Python CSI backend reads and parses that mounted JSON file. It does **not** call Secrets Manager through boto3 for DB credentials. Ensure the AWS provider's configured identity has permission to retrieve the secret (and decrypt it if customer-managed KMS is used). The application workload identity still needs S3 permissions.

The mounted JSON must contain `username` and `password` (or `DB_USER` and `DB_PASSWORD`).

## Health checks

- `/health/startup`: process startup check.
- `/health/live`: process liveness check; independent of RDS.
- `/health/ready`: checks RDS and returns 503 when it is unavailable.

Both deployment variants expose the same backend Service name, `backend-service`, in namespace `backend`. Deploy only one variant at a time into that namespace, or change the Service name/selector if running both simultaneously.

`deployment.yaml` is retained as the original generic example. For these two credential-specific deployments, apply the matching variant file above rather than applying every YAML file in this directory together.
