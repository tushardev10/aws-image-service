import importlib.util
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock


# ------------------ Lambda loader ------------------

def load_lambda(name, rel_path):
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", rel_path)
    )

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)

    # 🔑 required for unittest.mock.patch
    sys.modules[name] = module

    spec.loader.exec_module(module)
    return module


# ------------------ Environment ------------------

@pytest.fixture(autouse=True)
def env_vars():
    os.environ["ENDPOINT_URL"] = "http://localhost:4566"
    os.environ["AWS_ACCESS_KEY"] = "test"
    os.environ["AWS_SECRET_KEY"] = "test"
    os.environ["REGION"] = "us-east-1"
    os.environ["TABLE"] = "images"
    yield


# ------------------ Load lambda ------------------

list_lambda = load_lambda(
    "list_handler",
    "lambdas/list/handler.py"
)


# ------------------ Tests ------------------

@patch("list_handler.ddb")
def test_list_images_success(mock_ddb):
    table = MagicMock()
    mock_ddb.Table.return_value = table

    table.query.return_value = {
        "Items": [
            {
                "image_id": "img-1",
                "thumbnail": "thumb",
                "tags": ["profile"],
                "created_at": 123
            }
        ]
    }

    event = {
        "queryStringParameters": {
            "user_id": "user-1"
        }
    }

    response = list_lambda.handler(event, None)

    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["count"] == 1
    assert body["images"][0]["image_id"] == "img-1"


@patch("list_handler.ddb")
def test_list_with_tag_filter(mock_ddb):
    table = MagicMock()
    mock_ddb.Table.return_value = table

    table.query.return_value = {"Items": []}

    event = {
        "queryStringParameters": {
            "user_id": "user-1",
            "tag": "profile"
        }
    }

    response = list_lambda.handler(event, None)

    assert response["statusCode"] == 200

    # verify FilterExpression exists
    kwargs = table.query.call_args.kwargs
    assert "FilterExpression" in kwargs


@patch("list_handler.ddb")
def test_list_with_pagination(mock_ddb):
    table = MagicMock()
    mock_ddb.Table.return_value = table

    last_key = {"image_id": "img-9"}

    table.query.return_value = {
        "Items": [],
        "LastEvaluatedKey": last_key
    }

    event = {
        "queryStringParameters": {
            "user_id": "user-1",
            "last_key": json.dumps(last_key)
        }
    }

    response = list_lambda.handler(event, None)

    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["last_key"] == json.dumps(last_key)

    kwargs = table.query.call_args.kwargs
    assert kwargs["ExclusiveStartKey"] == last_key


def test_missing_user_id():
    response = list_lambda.handler(
        {"queryStringParameters": {}},
        None
    )

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["message"] == "user_id is required"


@patch("list_handler.ddb")
def test_ddb_exception_returns_500(mock_ddb):
    table = MagicMock()
    mock_ddb.Table.return_value = table

    table.query.side_effect = Exception("ddb failure")

    event = {
        "queryStringParameters": {
            "user_id": "user-1"
        }
    }

    response = list_lambda.handler(event, None)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert body["message"] == "internal_error"
