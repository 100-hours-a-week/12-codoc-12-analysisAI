# Monitoring Deployment (Separated Server)

This folder is deployable via AWS CodeDeploy to a dedicated monitoring host.

## What runs on monitoring server
- Prometheus
- Grafana
- Alertmanager
- Loki

## Required config (`deploy.env`)
- `AWS_REGION`: AWS region (e.g. `ap-northeast-2`)
- `MONITORING_EC2_TAG_KEY`: EC2 tag key used to discover analysis instances (default: `MonitoringTarget`)
- `MONITORING_EC2_TAG_VALUE`: EC2 tag value used to discover analysis instances (default: `analysis`)
- `GRAFANA_ADMIN_USER` (optional, default `admin`)
- `GRAFANA_ADMIN_PASSWORD` (optional, default `admin`)

## Deploy flow
1. CI uploads zipped `monitoring/` bundle to S3.
2. CodeDeploy installs bundle to `/home/ubuntu/monitoring/codedeploy-bundle`.
3. `deploy-scripts/deploy_stack.sh` renders Prometheus discovery settings and runs compose.

## Autoscaling-friendly discovery
Prometheus uses `ec2_sd_configs` and discovers running analysis instances by EC2 tag.

Tag your analysis instances/launch template:
- `MonitoringTarget=analysis`

## Analysis server exporters
Run on analysis server:

```bash
./scripts/monitoring/start_analysis_exporters.sh
# GPU server:
./scripts/monitoring/start_analysis_exporters.sh --gpu
```

Stop:

```bash
./scripts/monitoring/stop_analysis_exporters.sh
```
