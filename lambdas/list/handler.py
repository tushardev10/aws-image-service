import json
from boto3.dynamodb.conditions import Key
from datetime import datetime

import boto3

AWS_CONFIG = {
    "endpoint_url": "http://localhost:4566",
    "aws_access_key_id": "test",
    "aws_secret_access_key": "test",
    "region_name": "us-east-1"
}

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

BUCKET = "images-bucket"
TABLE = "images"

def handler(event, context):
    params = event.get("queryStringParameters") or {}
    user_id = params.get("user_id")
    limit = int(params.get("limit", 20))

    table = ddb.Table(TABLE)

    if user_id:
        # Query via GSI (recommended)
        response = table.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(user_id),
            Limit=limit,
            ScanIndexForward=False
        )
        items = response.get("Items", [])
    else:
        # Fallback: scan (not ideal, but acceptable for demo)
        response = table.scan(Limit=limit)
        items = response.get("Items", [])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "count": len(items),
            "images": items
        })
    }
