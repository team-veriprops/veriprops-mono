# veriprops BACKEND
FastAPI Backend app

## EXTERNAL SERVICES USED
### Google
- veriprops-contract-bot@veriprops-ff515.iam.gserviceaccount.com
* docs.googleapis.com
* drive.googleapis.com

### AWS
* S3

### Aiven.io
* Postgres



## Install
pip install -r requirements.txt
## Docker Run
docker compose up

## Test locally (in-memory DB)
set appodus_active_env=test && pip install -r test-requirements.txt && alembic upgrade head && pytest

# Alembic
alembic upgrade head
set appodus_active_env=test && alembic upgrade head
$env:appodus_active_env="local"; alembic upgrade head; pytest
set appodus_active_env=dev && alembic revision -m ""
set appodus_active_env=dev && alembic revision --autogenerate -m ""
$env:appodus_active_env="local"; alembic revision --autogenerate -m "auto_generated"



## Contracts S3 Policy
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::your-contract-bucket/*"
        }
    ]
}


## 
Change: pwd_context = CryptContext(schemes=["sha256_crypt"])
To: pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")