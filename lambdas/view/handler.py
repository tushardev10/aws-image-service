import json
import boto3
import traceback
import logging
import os

# ------------------ Config ------------------

AWS_CONFIG = {
    "endpoint_url": os.environ.get("ENDPOINT_URL"),
    "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY"),
    "aws_secret_access_key": os.environ.get("AWS_SECRET_KEY"),
    "region_name": os.environ.get("REGION")
}

BUCKET = os.environ["BUCKET"]
TABLE = os.environ["TABLE"]
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# ------------------ Clients ------------------

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# ------------------ Handler ------------------

def handler(event, context):
    try:
        path = event.get("pathParameters") or {}
        image_id = path.get("image_id")

        if not image_id:
            return _bad_request("image_id is required")

        table = ddb.Table(TABLE)
        response = table.get_item(Key={"image_id": image_id})

        if "Item" not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({"message": "Image not found"})
            }

        item = response["Item"]

        # ---------- Allow only READY images ----------
        if item.get("status") != "READY":
            return {
                "statusCode": 409,
                "body": json.dumps({
                    "message": f"Image not ready (status={item.get('status')})"
                })
            }

        s3_key = item.get("s3_key")
        if not s3_key:
            raise ValueError("Missing s3_key in DB record")

        # ---------- Generate download URL ----------
        presigned_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": BUCKET,
                "Key": s3_key
            },
            ExpiresIn=300  # 5 minutes
        )

        # ---------- Trim metadata ----------
        metadata = {
            "image_id": item.get("image_id"),
            "user_id": item.get("user_id"),
            "tags": item.get("tags", []),
            "created_at": item.get("created_at"),
            "thumbnail": item.get("thumbnail")
        }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "image": metadata,
                "url": presigned_url.replace("localstack:4566", "localhost:8080")
            })
        }

    except Exception as e:
        logger.error("View image failed")
        logger.error(str(e))
        logger.error(traceback.format_exc())

        return {
            "statusCode": 500,
            "body": json.dumps({"message": "internal_error"})
        }


def _bad_request(msg):
    return {
        "statusCode": 400,
        "body": json.dumps({"message": msg})
    }
