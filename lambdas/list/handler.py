import json
from boto3.dynamodb.conditions import Key, Attr
import boto3
import traceback
import logging
import os

AWS_CONFIG = {
    "endpoint_url": os.environ["ENDPOINT_URL"],
    "aws_access_key_id": os.environ["AWS_ACCESS_KEY"],
    "aws_secret_access_key": os.environ["AWS_SECRET_KEY"],
    "region_name": os.environ["REGION"]
}

TABLE = os.environ["TABLE"]
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

ddb = boto3.resource("dynamodb", **AWS_CONFIG)

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)


def handler(event, context):
    try:
        params = event.get("queryStringParameters") or {}

        user_id = params.get("user_id")
        tag = params.get("tag")              # single tag filter
        limit = int(params.get("limit", 20))
        last_key = params.get("last_key")    # pagination

        if not user_id:
            return _bad_request("user_id is required")

        table = ddb.Table(TABLE)

        # ---------- Base query (fast, indexed) ----------

        query_kwargs = {
            "IndexName": "user_id-index",
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "Limit": limit,
            "ScanIndexForward": False,  # latest first
            "ProjectionExpression": (
                "image_id, thumbnail, tags, created_at"
            ),
            "FilterExpression": Attr("status").eq("READY")
        }

        # ---------- Optional tag filter ----------

        if tag:
            query_kwargs["FilterExpression"] = (
                query_kwargs["FilterExpression"]
                & Attr("tags").contains(tag)
            )

        # ---------- Pagination ----------

        if last_key:
            query_kwargs["ExclusiveStartKey"] = json.loads(last_key)

        response = table.query(**query_kwargs)

        items = response.get("Items", [])

        return {
            "statusCode": 200,
            "body": json.dumps({
                "count": len(items),
                "images": items,
                "last_key": json.dumps(response["LastEvaluatedKey"])
                if "LastEvaluatedKey" in response else None
            })
        }

    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "internal_error"
            })
        }


def _bad_request(msg):
    return {
        "statusCode": 400,
        "body": json.dumps({"message": msg})
    }
