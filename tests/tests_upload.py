from moto import mock_s3, mock_dynamodb
import boto3
from handlers.upload import handler

@mock_s3
@mock_dynamodb
def test_upload():
    boto3.client("s3").create_bucket(Bucket="image-bucket")
    dynamodb = boto3.resource("dynamodb")

    dynamodb.create_table(
        TableName="images",
        KeySchema=[
            {"AttributeName": "image_id", "KeyType": "HASH"},
            {"AttributeName": "user_id", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "image_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    event = {
        "body": {
            "user_id": "u1",
            "file": b"test",
            "content_type": "image/png",
            "tags": "a,b"
        }
    }

    res = handler(event, None)
    assert res["statusCode"] == 201
