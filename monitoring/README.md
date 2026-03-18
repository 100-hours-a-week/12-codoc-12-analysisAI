# 모니터링 배포 안내

이 디렉터리는 전용 모니터링 서버에 AWS CodeDeploy로 배포할 수 있는 번들이다.

## 모니터링 서버에서 실행되는 구성
- Prometheus
- Grafana
- Alertmanager
- Loki

## 필수 설정 (`deploy.env`)
- `AWS_REGION`: AWS 리전 예시 `ap-northeast-2`
- `MONITORING_EC2_TAG_KEY`: analysis 인스턴스 탐색에 사용할 EC2 태그 키, 기본값 `MonitoringTarget`
- `MONITORING_EC2_TAG_VALUE`: analysis 인스턴스 탐색에 사용할 EC2 태그 값, 기본값 `analysis`
- `GRAFANA_ADMIN_USER`: 선택값, 기본값 `admin`
- `GRAFANA_ADMIN_PASSWORD`: 선택값, 기본값 `admin`
- `DISCORD_WEBHOOK_URL`: 선택값, 설정하면 Alertmanager가 Discord로 알림을 보내고 비어 있으면 `noop` receiver를 유지한다

## 배포 흐름
1. CI가 `monitoring/` 번들을 zip으로 묶어 S3에 업로드한다.
2. CodeDeploy가 번들을 `/home/ubuntu/monitoring/codedeploy-bundle` 경로에 설치한다.
3. `deploy-scripts/deploy_stack.sh`가 Prometheus 서비스 디스커버리 설정을 렌더링하고 compose를 실행한다.
4. `DISCORD_WEBHOOK_URL`이 설정되어 있으면 compose 실행 전에 Alertmanager 설정을 Discord receiver 기준으로 렌더링한다.

## 오토스케일링 친화적 디스커버리
Prometheus는 `ec2_sd_configs`를 사용해서 EC2 태그 기준으로 실행 중인 analysis 인스턴스를 자동 탐색한다.

analysis 인스턴스 또는 Launch Template에는 아래 태그가 있어야 한다.
- `MonitoringTarget=analysis`

## Analysis 서버 exporter 실행
analysis 서버에서 아래 명령으로 exporter를 실행한다.

```bash
./scripts/monitoring/start_analysis_exporters.sh
# GPU 서버인 경우
./scripts/monitoring/start_analysis_exporters.sh --gpu
```

중지할 때는 아래 명령을 사용한다.

```bash
./scripts/monitoring/stop_analysis_exporters.sh
```
