#!/bin/bash
set -e

export PATH=$PATH:/usr/bin:/usr/local/bin

#AWS="aws --endpoint-url=http://localhost:4566"
AWS="/usr/local/bin/aws --endpoint-url=http://localhost:4566"
REGION="us-east-1"

BUCKET="images-bucket"
LAMBDA_BUCKET="lambda-code-bucket"
TABLE="images"
ROLE_ARN="arn:aws:iam::000000000000:role/lambda-role"

RUNTIME="python3.10"
HANDLER="handler.handler"
TIMEOUT=10
MEMORY=256

echo "========== LocalStack Image Service Init =========="

# -----------------------------
# S3
# -----------------------------
create_s3_buckets() {
  echo "Creating S3 buckets..."
  $AWS s3 mb s3://$BUCKET || true
  $AWS s3 mb s3://$LAMBDA_BUCKET || true
}

# -----------------------------
# DynamoDB
# -----------------------------
create_dynamodb_table() {
  echo "Creating DynamoDB table: $TABLE"

  $AWS dynamodb create-table \
    --table-name $TABLE \
    --attribute-definitions \
        AttributeName=image_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
    --key-schema \
        AttributeName=image_id,KeyType=HASH \
    --global-secondary-indexes '[
      {
        "IndexName":"user_id-index",
        "KeySchema":[
          {"AttributeName":"user_id","KeyType":"HASH"},
          {"AttributeName":"created_at","KeyType":"RANGE"}
        ],
        "Projection":{"ProjectionType":"ALL"},
        "ProvisionedThroughput":{"ReadCapacityUnits":5,"WriteCapacityUnits":5}
      }
    ]' \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region $REGION || true
}

# -----------------------------
# Lambda
# -----------------------------
create_lambda() {
  NAME=$1
  ZIP_NAME=$2
  HANDLER=$3

  echo "Creating Lambda: $NAME"

  $AWS lambda create-function \
    --function-name $NAME \
    --runtime $RUNTIME \
    --handler $HANDLER \
    --timeout $TIMEOUT \
    --memory-size $MEMORY \
    --role $ROLE_ARN \
    --environment "Variables={
      BUCKET=$BUCKET,
      TABLE=$TABLE,
      LOG_LEVEL=INFO
    }" \
    --code S3Bucket=$LAMBDA_BUCKET,S3Key=$ZIP_NAME \
    || echo "Lambda $NAME already exists"
}


# --------------------------------------------------
# Package & Upload Lambdas
# --------------------------------------------------

package_and_upload_lambdas() {
  echo "Packaging and uploading Lambda code..."

  cd /opt/lambdas

  cd upload  && zip -r ../upload.zip  handler.py && cd ..
  cd list    && zip -r ../list.zip    handler.py && cd ..
  cd view    && zip -r ../view.zip    handler.py && cd ..
  cd delete  && zip -r ../delete.zip  handler.py && cd ..

  $AWS s3 cp upload.zip  s3://$LAMBDA_BUCKET/
  $AWS s3 cp list.zip    s3://$LAMBDA_BUCKET/
  $AWS s3 cp view.zip    s3://$LAMBDA_BUCKET/
  $AWS s3 cp delete.zip  s3://$LAMBDA_BUCKET/
}


# -----------------------------
# API Gateway
# -----------------------------
create_api_gateway() {
  echo "Creating API Gateway"

  API_ID=$($AWS apigateway create-rest-api \
    --name image-api \
    --query id \
    --region $REGION \
    --output text)

  sleep 3

  ROOT_ID=$($AWS apigateway get-resources \
    --rest-api-id $API_ID \
    --query 'items[0].id' \
    --region $REGION \
    --output text)

  echo "API_ID=$API_ID"
  echo "ROOT_ID=$ROOT_ID"

  create_resource_and_method "$API_ID" "$ROOT_ID" "images" "POST"  "upload-image"
  create_resource_and_method "$API_ID" "$ROOT_ID" "images" "GET"   "list-images"

  IMAGE_ID_RES=$($AWS apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_ID \
    --region $REGION \
    --path-part "{image_id}" \
    --query id \
    --output text)

  create_method "$API_ID" "$IMAGE_ID_RES" "GET"    "view-image"
  create_method "$API_ID" "$IMAGE_ID_RES" "DELETE" "delete-image"

  $AWS apigateway create-deployment \
    --rest-api-id $API_ID \
    --region $REGION \
    --stage-name dev

  echo "API deployed: http://localhost:4566/restapis/$API_ID/dev/_user_request_"
}

create_resource_and_method() {
  API_ID=$1
  PARENT_ID=$2
  PATH=$3
  METHOD=$4
  LAMBDA=$5

  RES_ID=$($AWS apigateway get-resources --rest-api-id $API_ID --query "items[?path=='/$PATH'].id" --region $REGION --output text)

  if [ -z "$RES_ID" ]; then
    RES_ID=$($AWS apigateway create-resource \
      --rest-api-id $API_ID \
      --parent-id $PARENT_ID \
      --path-part $PATH \
      --region $REGION \
      --query id \
      --output text)
  fi

  create_method "$API_ID" "$RES_ID" "$METHOD" "$LAMBDA"
}

create_method() {
  API_ID=$1
  RES_ID=$2
  METHOD=$3
  LAMBDA=$4

  $AWS apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RES_ID \
    --http-method $METHOD \
    --authorization-type NONE \
    --region $REGION

  $AWS apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RES_ID \
    --http-method $METHOD \
    --region $REGION \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$LAMBDA/invocations
}

# -----------------------------
# EXECUTION
# -----------------------------
create_s3_buckets
create_dynamodb_table
package_and_upload_lambdas

create_lambda upload-image upload.zip handler.handler
create_lambda list-images   list.zip   handler.handler
create_lambda view-image   view.zip   handler.handler
create_lambda delete-image delete.zip handler.handler

create_api_gateway

echo "========== INIT COMPLETE =========="

