import os
import json
import uuid
import importlib.util
import boto3
import pytest
from datetime import datetime

# ------------------ Load lambda dynamically ------------------

LAMBDA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "lambdas",
        "view",
        "handler.py"
    )
)

spec = importlib.util.spec_from_file_location("view_handler", LAMBDA_PATH)
view_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(view_handler)

handler = view_handler.handler

# ------------------ AWS clients ------------------

AWS_CONFIG = {
    "endpoint_url": os.environ["ENDPOINT_URL"],
    "aws_access_key_id": os.environ["AWS_ACCESS_KEY"],
    "aws_secret_access_key": os.environ["AWS_SECRET_KEY"],
    "region_name": os.environ["REGION"],
}

s3 = boto3.client("s3", **AWS_CONFIG)
ddb = boto3.resource("dynamodb", **AWS_CONFIG)

BUCKET = os.environ["BUCKET"]
TABLE = os.environ["TABLE"]

# ------------------ Fixtures ------------------

@pytest.fixture
def image_id():
    return str(uuid.uuid4())


@pytest.fixture
def ddb_table():
    return ddb.Table(TABLE)


@pytest.fixture
def ready_image(ddb_table, image_id):
    item = {
        "image_id": image_id,
        "user_id": "user_123",
        "status": "READY",
        "s3_key": f"images/{image_id}.jpg",
        "tags": ["cat"],
        "created_at": datetime.utcnow().isoformat(),
        "thumbnail": "thumb.jpg"
    }
    ddb_table.put_item(Item=item)
    return item


@pytest.fixture
def processing_image(ddb_table, image_id):
    item = {
        "image_id": image_id,
        "user_id": "user_123",
        "status": "PROCESSING"
    }
    ddb_table.put_item(Item=item)
    return item


# ------------------ Tests ------------------

def test_missing_image_id():
    event = {"pathParameters": {}}
    resp = handler(event, None)

    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["message"] == "image_id is required"


def test_image_not_found(image_id):
    event = {"pathParameters": {"image_id": image_id}}
    resp = handler(event, None)

    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert body["message"] == "Image not found"


def test_image_not_ready(processing_image):
    event = {
        "pathParameters": {
            "image_id": processing_image["image_id"]
        }
    }

    resp = handler(event, None)

    assert resp["statusCode"] == 409
    body = json.loads(resp["body"])
    assert "Image not ready" in body["message"]


def test_success_ready_image(ready_image):
    # upload dummy object so presigned URL works
    s3.put_object(
        Bucket=BUCKET,
        Key=ready_image["s3_key"],
        Body=b"dummy"
    )

    event = {
        "pathParameters": {
            "image_id": ready_image["image_id"]
        }
    }

    resp = handler(event, None)

    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])

    assert "image" in body
    assert "url" in body

    image = body["image"]
    assert image["image_id"] == ready_image["image_id"]
    assert image["user_id"] == ready_image["user_id"]
    assert image["thumbnail"] == ready_image["thumbnail"]

    # nginx rewrite check
    assert "images/" in body["url"]
    assert ready_image["image_id"] in body["url"]
