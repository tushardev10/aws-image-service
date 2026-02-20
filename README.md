# Image Service (LocalStack)

## Run Docker Image
```sh
docker-compose up --build -d
```
This will make 2 docker containers up
- Localstack (for AWS intrastructure)
- Nginx (url simlification / redirection)

For stopping the containers

```bash
docker-compose down -v  
```

## Explanation
It contains 5 Lambdas.
1. pre-upload (for creating pre-signed url to upload image)
2. upload (confirm s3 upload and modify entry in table, gets triggered on s3 upload event)
3. list (to view multiple images based on user_id & tags)
4. view (view single image along with download pre-signed link)
5. delete (to delete the image and its record in db)

## Pre-Upload
POST http://localhost:8080/pre-upload

Sample Request and Response:

```bash
curl -X POST http://localhost:8080/ \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "user1",
           "file_name": "u1.jpg",
           "content_type": "image/jpeg",
           "tags": ["travelgoal", "scenic"]
         }'
```

```json
{"message": "upload_url_generated", "data": {"image_id": "2c25cec8-a28d-4a89-b1b8-ea0738f42bd7", "upload_url": "http://localhost:8080/images-bucket/user1/2c25cec8-a28d-4a89-b1b8-ea0738f42bd7.jpg?AWSAccessKeyId=test&Signature=TMEGfagWIafltxoAn54MYJZVo2o%3D&content-type=image%2Fjpeg&Expires=1770057028", "expires_in_seconds": 300}}
```

## Upload
Using the pre-signed url client can directly upload the image to s3 after which upload lambda gets triggered automatically with events call
PUT http://localhost:8080/images

Sample Request and Response:

```bash
curl -X PUT \
  -H "Content-Type: image/jpeg" \
  --upload-file ./u1.jpg \
  "http://localhost:8080/images-bucket/user1/2c25cec8-a28d-4a89-b1b8-ea0738f42bd7.jpg?AWSAccessKeyId=test&Signature=TMEGfagWIafltxoAn54MYJZVo2o%3D&content-type=image%2Fjpeg&Expires=1770057028"
```

```json
{"message": "Upload completed"}
```

## List
GET http://localhost:8080/images?user_id=123&tag=travel

Sample Request and Response:

```bash
curl -X GET "http://localhost:8080/images?user_id=user1&limit=10"
curl -X GET "http://localhost:8080/images?user_id=user1&tag=scenic"
```

```json
{"count": 1, "images": [{"created_at": "1770056728", "thumbnail": "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", "image_id": "2c25cec8-a28d-4a89-b1b8-ea0738f42bd7", "tags": ["travelgoal", "scenic"]}], "last_key": null}
```

## View
GET http://localhost:8080/images/{image_id}

Sample Request and Response:

```bash
curl -X GET http://localhost:8080/images/2c25cec8-a28d-4a89-b1b8-ea0738f42bd7
```

```json
{"image": {"image_id": "2c25cec8-a28d-4a89-b1b8-ea0738f42bd7", "user_id": "user1", "tags": ["travelgoal", "scenic"], "created_at": "1770056728", "thumbnail": "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"}, "url": "http://localhost:8080/images-bucket/user1/2c25cec8-a28d-4a89-b1b8-ea0738f42bd7.jpg?AWSAccessKeyId=test&Signature=ZGlpGGwE4SeZXChHqGpoiIeUMRc%3D&Expires=1770057257"}
```

## Delete
DELETE http://localhost:8080/images/{image_id}?user_id=123

Sample Request and Response:

```bash
curl -X DELETE http://localhost:8080/images/2c25cec8-a28d-4a89-b1b8-ea0738f42bd7
```

```json
{"message": "Image deleted successfully", "image_id": "2c25cec8-a28d-4a89-b1b8-ea0738f42bd7"}
```


## Test Cases:

- Create virtual environment and activate it.
```bash
python3 -n venv venv
source venv/bin/activate
```
- Install requirements.txt packages.
```bash
pip install -r requirements.txt
```
- export localstack Environment
```bash
source env.localstack
```
- Run pytests
```bash
pytest -v
```
