#!/usr/bin/env bash
# Validates every generated template with the AWS CloudFormation API. Needs AWS credentials
# (aws login / aws configure sso); it creates nothing. Templates over 51,200 bytes need --template-url.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/../cloudinfra-generated}"
REGION="${AWS_REGION:-us-east-1}"
aws sts get-caller-identity --query Account --output text >/dev/null
status=0
for template in "$OUT_DIR"/*-infra/template.yaml "$OUT_DIR/platform.yaml"; do
  if aws cloudformation validate-template --region "$REGION" --template-body "file://$template" >/dev/null; then
    echo "✓ ${template#$OUT_DIR/}"
  else
    echo "✗ ${template#$OUT_DIR/}"; status=1
  fi
done
exit $status
