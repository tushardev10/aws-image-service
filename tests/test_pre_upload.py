import json
import os
import uuid
import boto3
import pytest
import importlib.util
from datetime import datetime

# ------------------ Load Lambda Dynamically ------------------

LAMBDA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "lambdas",
        "pre-upload",
        "handler.py"
    )
)

spec = importlib.util.spec_from_file_location("pre_upload_handler", LAMBDA_PATH)
pre_upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pre_upload)

handler = pre_upload.handler

# ------------------ Config ------------------

AWS_CONFIG = {
    "endpoint_url": os.environ.get("ENDPOINT_URL", "http://localhost:4566"),
    "aws_access_key_id": "test",
    "aws_secret_access_key": "test",
    "region_name": "us-east-1",
}

BUCKET = os.environ.get("BUCKET", "images-bucket")
TABLE = os.environ.get("TABLE", "images")

# ------------------ AWS Clients ------------------

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

# ------------------ Fixtures ------------------

@pytest.fixture(scope="module", autouse=True)
def setup_aws_resources():
    """Ensure S3 bucket and DynamoDB table exist"""

    # S3 bucket
    try:
        s3.create_bucket(Bucket=BUCKET)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    except s3.exceptions.BucketAlreadyExists:
        pass

    # DynamoDB table
    existing_tables = [t.name for t in ddb.tables.all()]
    if TABLE not in existing_tables:
        ddb.create_table(
            TableName=TABLE,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "image_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "image_id", "KeyType": "HASH"},
            ],
        ).wait_until_exists()

    yield

# ------------------ Helpers ------------------

def call_lambda(body: dict):
    event = {
        "body": json.dumps(body)
    }
    return handler(event, None)

# ------------------ Tests ------------------

def test_pre_upload_success():
    response = call_lambda({
        "user_id": "user1",
        "file_name": "u1.jpg",
        "content_type": "image/jpeg",
        "tags": ["travel", "scenic"]
    })

    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["message"] == "upload_url_generated"

    data = body["data"]
    assert "image_id" in data
    assert "upload_url" in data
    assert data["expires_in_seconds"] == 300

    # Verify DB record
    table = ddb.Table(TABLE)
    item = table.get_item(
        Key={"image_id": data["image_id"]}
    )["Item"]

    assert item["status"] == "UPLOADING"
    assert item["user_id"] == "user1"
    assert "expires_at" in item


def test_pre_upload_missing_user_id():
    response = call_lambda({
        "tags": ["test"]
    })

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "user_id" in body["message"]


def test_pre_upload_tags_not_list():
    response = call_lambda({
        "user_id": "user1",
        "tags": "not-a-list"
    })

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "tags must be a list" in body["message"]


def test_pre_upload_duplicate_image_id_not_allowed(monkeypatch):
    """Force duplicate UUID to validate conditional write"""

    fixed_uuid = str(uuid.uuid4())

    monkeypatch.setattr(uuid, "uuid4", lambda: fixed_uuid)

    # First call → success
    first = call_lambda({
        "user_id": "user1",
        "tags": []
    })
    assert first["statusCode"] == 200

    # Second call → should fail
    second = call_lambda({
        "user_id": "user1",
        "tags": []
    })
    assert second["statusCode"] == 500
