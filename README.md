# Image Service (LocalStack)

## Upload
POST /images

Body:
- user_id
- file
- content_type
- tags

## List
GET /images?user_id=123&tag=travel

## View
GET /images/{image_id}?user_id=123

## Delete
DELETE /images/{image_id}?user_id=123
