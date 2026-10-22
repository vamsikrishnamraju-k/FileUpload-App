# Kubernetes health checks

- Startup probe: confirms the application has started; does not depend on RDS.
- Liveness probe: checks the application process; does not depend on RDS.
- Readiness probe: checks the RDS dependency; a failed check removes the pod from Service traffic without restarting it.
- Replace the image value in deployment.yaml with your ECR image.
