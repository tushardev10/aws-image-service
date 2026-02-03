import importlib.util
import os
import json
import io
import sys
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


def load_lambda(name, rel_path):
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", rel_path)
    )

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)

    # 🔑 THIS LINE FIXES YOUR ERROR
    sys.modules[name] = module

    spec.loader.exec_module(module)
    return module


upload = load_lambda(
    "upload_handler",
    "lambdas/upload/handler.py"
)


def test_generate_thumbnail():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    import imageio.v3 as iio
    buf = io.BytesIO()
    iio.imwrite(buf, img, format="JPEG")

    result = upload.generate_thumbnail(buf.getvalue())
    assert isinstance(result, str)


@patch("upload_handler.generate_thumbnail")
@patch("upload_handler.ddb")
@patch("upload_handler.s3")
def test_upload_success(mock_s3, mock_ddb, mock_thumb):
    mock_thumb.return_value = "fake_base64_thumb"

    table = MagicMock()
    mock_ddb.Table.return_value = table

    table.get_item.return_value = {
        "Item": {"image_id": "img-1", "s3_key": "a.jpg"}
    }

    mock_s3.get_object.return_value = {
        "ContentType": "image/jpeg",
        "Body": io.BytesIO(b"not_used_anymore")
    }

    event = {"body": json.dumps({"image_id": "img-1"})}
    response = upload.handler(event, None)

    assert response["statusCode"] == 200
    table.update_item.assert_called_once()
