import boto3
import os
import logging
import traceback
import base64
import io
import json
from datetime import datetime
from urllib.parse import unquote_plus
import imageio.v3 as iio
import numpy as np
import base64
import io


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

# ------------------ Clients ------------------

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# ------------------ Thumbnail ------------------

def generate_thumbnail(image_bytes):
    # Read image into numpy array
    img = iio.imread(image_bytes)
    
    # Compute new size
    h, w = img.shape[:2]
    max_dim = 120
    if h > w:
        new_h = max_dim
        new_w = int((w / h) * max_dim)
    else:
        new_w = max_dim
        new_h = int((h / w) * max_dim)
    
    # Resize using simple nearest neighbor
    row_idx = (np.linspace(0, h-1, new_h)).astype(int)
    col_idx = (np.linspace(0, w-1, new_w)).astype(int)
    thumbnail = img[row_idx][:, col_idx]
    
    # Encode as JPEG in-memory
    buf = io.BytesIO()
    iio.imwrite(buf, thumbnail, format="JPEG")
    
    # Base64 encode
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ------------------ Handler ------------------

def handler(event, context):
    image_id = None

    # ---------- Getting image from S3 ----------
    table = ddb.Table(TABLE)

    for record in event.get("Records", []):
        try:
            bucket_name = record["s3"]["bucket"]["name"]
            s3_key = unquote_plus(record["s3"]["object"]["key"])
            image_id = os.path.splitext(os.path.basename(s3_key))[0]

            logger.info(f"Processing S3 object: s3://{bucket_name}/{s3_key}")
            obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
            content_type = obj.get("ContentType", "")
            logger.info(f"Content type recieved")

            if not content_type.startswith("image/"):
                raise ValueError(f"Invalid content type: {content_type}")

            image_bytes = obj["Body"].read()
            

            if not image_bytes:
                raise ValueError("Uploaded file is empty")

            # ---------- Generate thumbnail ----------

            thumbnail_b64 = generate_thumbnail(image_bytes)

            # ---------- Update DB ----------

            table.update_item(
                Key={"image_id": image_id},
                UpdateExpression="""
                    SET #s = :s,
                        thumbnail = :t,
                        updated_at = :u
                    REMOVE expires_at
                """,
                ExpressionAttributeNames={
                    "#s": "status"
                },
                ExpressionAttributeValues={
                    ":s": "READY",
                    ":t": thumbnail_b64,
                    ":u": int(datetime.utcnow().timestamp())
                }
            )

            logger.info(f"Upload completed for image_id={image_id}")

        except Exception as e:
            logger.error("Upload completion failed")
            logger.error(str(e))
            logger.error(traceback.format_exc())

            if image_id:
                try:
                    table.update_item(
                        Key={"image_id": image_id},
                        UpdateExpression="""
                            SET #s = :s,
                                error = :e,
                                expires_at = :ttl
                        """,
                        ExpressionAttributeNames={
                            "#s": "status"
                        },
                        ExpressionAttributeValues={
                            ":s": "FAILED",
                            ":e": str(e),
                            ":ttl": int(datetime.utcnow().timestamp()) + 3600
                        }
                    )
                except Exception:
                    logger.error("Failed to update FAILED status")

            return {
                "statusCode": 500,
                "body": json.dumps({"message": "Internal server error"})
            }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Upload completed"})
    }
