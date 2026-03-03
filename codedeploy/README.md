# CodeDeploy bundle

This folder is zipped and uploaded to S3, then used by AWS CodeDeploy.

## Required on target EC2 (AMI)

1. CodeDeploy agent installed and running
2. Docker installed and runnable by `ubuntu`
3. IAM role includes:
   - AmazonEC2RoleforAWSCodeDeploy
   - AmazonEC2ContainerRegistryReadOnly
4. `/home/ubuntu/analysis/shared/.env` (optional app env)
5. `/home/ubuntu/analysis/shared/deploy.env` is created by CD workflow from secrets

## Local test

```bash
cd codedeploy
zip -r /tmp/codoc-deploy.zip .
aws s3 cp /tmp/codoc-deploy.zip s3://<bucket>/<key>
aws deploy create-deployment \
  --application-name <app> \
  --deployment-group-name <group> \
  --revision "revisionType=S3,s3Location={bucket=<bucket>,key=<key>,bundleType=zip}"
```
