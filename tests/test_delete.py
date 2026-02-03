import os
import sys
import json
import io
import importlib.util
import pytest
from unittest.mock import patch, MagicMock

# ---------------- Load delete lambda dynamically ----------------

LAMBDA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "lambdas",
        "delete",
        "handler.py"
    )
)

spec = importlib.util.spec_from_file_location("delete_handler", LAMBDA_PATH)
delete_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delete_handler)

# Add to sys.modules so patch decorators work
sys.modules["delete_handler"] = delete_handler

handler = delete_handler.handler
BAD_REQUEST_MSG = "image_id is required"

# ---------------- Tests ----------------

@patch("delete_handler.ddb")
@patch("delete_handler.s3")
def test_missing_image_id(mock_s3, mock_ddb):
    event = {"pathParameters": {}}
    resp = handler(event, None)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["message"] == BAD_REQUEST_MSG

@patch("delete_handler.ddb")
@patch("delete_handler.s3")
def test_image_not_found(mock_s3, mock_ddb):
    table_mock = MagicMock()
    mock_ddb.Table.return_value = table_mock
    table_mock.get_item.return_value = {}  # No "Item"

    event = {"pathParameters": {"image_id": "img-123"}}
    resp = handler(event, None)

    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert body["message"] == "Image not found"

@patch("delete_handler.ddb")
@patch("delete_handler.s3")
def test_delete_success(mock_s3, mock_ddb):
    table_mock = MagicMock()
    mock_ddb.Table.return_value = table_mock
    mock_s3.delete_object.return_value = {}

    # Mock DB fetch
    table_mock.get_item.return_value = {
        "Item": {"image_id": "img-123", "s3_key": "images/img-123.jpg"}
    }

    event = {"pathParameters": {"image_id": "img-123"}}
    resp = handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["message"] == "Image deleted successfully"
    assert body["image_id"] == "img-123"

    table_mock.delete_item.assert_called_once()
    mock_s3.delete_object.assert_called_once_with(
        Bucket=os.environ.get("BUCKET"), Key="images/img-123.jpg"
    )

@patch("delete_handler.ddb")
@patch("delete_handler.s3")
def test_s3_delete_failure_does_not_fail(mock_s3, mock_ddb):
    table_mock = MagicMock()
    mock_ddb.Table.return_value = table_mock

    # Simulate S3 delete throwing error
    mock_s3.delete_object.side_effect = Exception("S3 down")

    table_mock.get_item.return_value = {
        "Item": {"image_id": "img-123", "s3_key": "images/img-123.jpg"}
    }

    event = {"pathParameters": {"image_id": "img-123"}}
    resp = handler(event, None)

    # Should still succeed in deleting DB record
    assert resp["statusCode"] == 200
    table_mock.delete_item.assert_called_once()
    mock_s3.delete_object.assert_called_once()

@patch("delete_handler.ddb")
@patch("delete_handler.s3")
def test_ddb_delete_exception_returns_500(mock_s3, mock_ddb):
    table_mock = MagicMock()
    mock_ddb.Table.return_value = table_mock

    table_mock.get_item.return_value = {
        "Item": {"image_id": "img-123", "s3_key": "images/img-123.jpg"}
    }

    # DB delete throws
    table_mock.delete_item.side_effect = Exception("DB failure")

    event = {"pathParameters": {"image_id": "img-123"}}
    resp = handler(event, None)

    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert body["message"] == "internal_error"
