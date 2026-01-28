import json
import uuid
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
    try:
        print("Entering upload handler")
        print("EVENT:", json.dumps(event))
        print("AWS_CONFIG:", AWS_CONFIG)
        print("BUCKET:", BUCKET)

        image_id = str(uuid.uuid4())
        body = json.loads(event["body"])

        user_id = body["user_id"]
        image_data = body["image"]  # base64 (simplified)

        key = f"{user_id}/{image_id}.jpg"

        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=image_data.encode()
        )
        print("S3 done")
        table = ddb.Table(TABLE)
        table.put_item(Item={
            "image_id": image_id,
            "user_id": user_id,
            "s3_key": key
        })

        return {
            "statusCode": 201,
            "body": json.dumps({"message":"success","data":{"image_id": image_id}})
        }
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"message":f"{e}","data":{}})
        }