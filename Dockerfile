FROM localstack/localstack:1.4.0

# Where LocalStack expects init scripts
WORKDIR /etc/localstack/init/ready.d

# Enable local lambda execution (NO docker.sock)
ENV SERVICES=lambda,apigateway,s3,dynamodb,iam,logs
ENV LAMBDA_RUNTIME_EXECUTOR=local
ENV AWS_DEFAULT_REGION=us-east-1
ENV AWS_ACCESS_KEY_ID=test
ENV AWS_SECRET_ACCESS_KEY=test
ENV DEBUG=1


RUN pip install awscli

# Copy init script
COPY init.sh /etc/localstack/init/ready.d/init.sh

# Copy lambda source code
COPY lambdas /opt/lambdas

# Make init.sh executable
RUN chmod +x /etc/localstack/init/ready.d/init.sh