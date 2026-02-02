import json
import uuid
import boto3
import logging
import os
from datetime import datetime, timedelta

# ------------------ Config ------------------

AWS_CONFIG = {
    "endpoint_url": os.environ.get("ENDPOINT_URL"),
    "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY"),
    "aws_secret_access_key": os.environ.get("AWS_SECRET_KEY"),
    "region_name": os.environ.get("REGION"),
}

BUCKET = os.environ["BUCKET"]
TABLE = os.environ["TABLE"]
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

UPLOAD_URL_TTL_SECONDS = 300          # presigned URL validity
UPLOAD_RECORD_TTL_MINUTES = 10        # DB cleanup window

# ------------------ Clients ------------------

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# ------------------ Handler ------------------

def handler(event, context):
    try:
        if "body" not in event:
            return _bad_request("Missing request body")

        body = json.loads(event["body"])

        user_id = body.get("user_id")
        tags = body.get("tags", [])

        if not user_id:
            return _bad_request("user_id is required")

        if not isinstance(tags, list):
            return _bad_request("tags must be a list")

        # ---------- Create identifiers ----------

        image_id = str(uuid.uuid4())
        s3_key = f"{user_id}/{image_id}.jpg"

        # ---------- TTL (only for UPLOADING state) ----------

        expires_at = int(
            (datetime.utcnow() + timedelta(minutes=UPLOAD_RECORD_TTL_MINUTES))
            .timestamp()
        )

        # ---------- Generate pre-signed URL ----------

        presigned_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET,
                "Key": s3_key,
                "ContentType": "image/jpeg",
            },
            ExpiresIn=UPLOAD_URL_TTL_SECONDS,
        )

        # ---------- Persist INIT record ----------

        table = ddb.Table(TABLE)
        table.put_item(
            Item={
                "image_id": image_id,
                "user_id": user_id,
                "s3_key": s3_key,
                "tags": tags,
                "status": "UPLOADING",
                "expires_at": expires_at,   # TTL applies ONLY now
                "created_at": str(int(datetime.utcnow().timestamp())),
            },
            ConditionExpression="attribute_not_exists(image_id)"
        )

        # ---------- Response ----------

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "upload_url_generated",
                "data": {
                    "image_id": image_id,
                    "upload_url": presigned_url.replace("localstack:4566", "localhost:8080"),
                    "expires_in_seconds": UPLOAD_URL_TTL_SECONDS
                }
            })
        }

    except Exception as e:
        logger.exception("Upload init failed")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "internal_error",
                "error": str(e)
            })
        }

# ------------------ Helpers ------------------

def _bad_request(msg):
    return {
        "statusCode": 400,
        "body": json.dumps({
            "message": msg
        })
    }
