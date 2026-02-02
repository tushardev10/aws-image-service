#!/bin/sh
set -e

echo "Waiting for API Gateway image-api to be ready..."

while true; do
  API_ID=$(aws apigateway get-rest-apis \
    --endpoint-url=http://localstack:4566 \
    --query "items[?name=='image-api'].id | [0]" \
    --output text 2>/dev/null || true)

  if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
    break
  fi

  echo "API Gateway not ready yet, retrying..."
  sleep 2
done

export API_ID
echo "API Gateway ready. Using API_ID=$API_ID"

exec /docker-entrypoint.sh "$@"
