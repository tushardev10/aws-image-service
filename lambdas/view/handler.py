import json
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
    image_id = event["pathParameters"]["image_id"]

    table = ddb.Table(TABLE)
    response = table.get_item(Key={"image_id": image_id})

    if "Item" not in response:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Image not found"})
        }

    item = response["Item"]

    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": BUCKET,
            "Key": item["s3_key"]
        },
        ExpiresIn=300
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "image_id": image_id,
            "url": presigned_url,
            "metadata": item
        })
    }
