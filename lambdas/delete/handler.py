import json
import boto3
import traceback
import logging
import os
from datetime import datetime

AWS_CONFIG = {
    "endpoint_url": os.environ.get("ENDPOINT_URL"),
    "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY"),
    "aws_secret_access_key": os.environ.get("AWS_SECRET_KEY"),
    "region_name": os.environ.get("REGION")
}

BUCKET = os.environ["BUCKET"]
TABLE = os.environ["TABLE"]
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)


def handler(event, context):
    try:
        path = event.get("pathParameters") or {}
        image_id = path.get("image_id")

        if not image_id:
            return _bad_request("image_id is required")

        table = ddb.Table(TABLE)

        # ---------- Fetch record ----------
        response = table.get_item(Key={"image_id": image_id})

        if "Item" not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({"message": "Image not found"})
            }

        item = response["Item"]
        s3_key = item.get("s3_key")

        # ---------- Delete from S3 (idempotent) ----------
        if s3_key:
            try:
                s3.delete_object(
                    Bucket=BUCKET,
                    Key=s3_key
                )
            except Exception as e:
                # Don't fail DB delete due to S3 glitch
                logger.warning(f"S3 delete failed for {s3_key}: {e}")

        # ---------- Delete from DynamoDB ----------
        table.delete_item(
            Key={"image_id": image_id},
            ConditionExpression="attribute_exists(image_id)"
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Image deleted successfully",
                "image_id": image_id
            })
        }

    except Exception as e:
        logger.error("Image delete failed")
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
