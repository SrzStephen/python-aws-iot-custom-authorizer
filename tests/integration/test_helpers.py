import functools
import urllib.request
from datetime import datetime
from os import getenv
from pathlib import Path
from time import sleep
from typing import Generator, TypedDict
from uuid import uuid4

import boto3
import pytest
from mypy_boto3_cloudformation import CloudFormationServiceResource
from mypy_boto3_dynamodb import DynamoDBServiceResource
from mypy_boto3_iot import IoTClient

from src.authorizer.authorizer.types import DynamoModel

stack_name = getenv("STACK_NAME", "authorizer")
iot_client: IoTClient = boto3.client("iot")
cloudformation_client: CloudFormationServiceResource = boto3.resource("cloudformation")
time_format = datetime.now().strftime("%m%d%Y%H%M")
aws_endpoint = iot_client.describe_endpoint(endpointType="iot:Data-ATS")[
    "endpointAddress"
]


def uuid_partial() -> str:
    return str(uuid4()).replace("-", "")


def get_val() -> str:
    return f"int{time_format}"


test_user = get_val() + uuid_partial()
test_pass = get_val() + uuid_partial()
test_client = get_val() + uuid_partial()
test_topic = f"integration/{uuid_partial()}".replace("-", "")


def calltracker(func):
    # from https://dzone.com/articles/python-how-to-tell-if-a-function-has-been-called
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.has_been_called = True
        return func(*args, **kwargs)

    wrapper.has_been_called = False
    return wrapper


# A check that calltracker works as expected
@calltracker
def function_1_calltracker():
    pass


@calltracker
def function_2_caltracker():
    pass


def test_calltracker():
    function_1_calltracker()
    assert function_1_calltracker.has_been_called  # type: ignore
    assert function_2_caltracker.has_been_called is False  # type: ignore
    function_2_caltracker()
    assert function_2_caltracker.has_been_called  # type: ignore


@pytest.fixture(scope="session")
def get_aws_ca_cert() -> Path:
    aws_ca = Path(__file__).parent / "awsCA.pem"
    urllib.request.urlretrieve(
        "https://www.amazontrust.com/repository/AmazonRootCA1.pem", aws_ca.absolute()
    )
    yield aws_ca
    # teardown
    aws_ca.unlink()


@pytest.fixture(scope="session")
def generate_table(stack_params) -> Generator[DynamoModel, None, None]:
    dynamo: DynamoDBServiceResource = boto3.resource(service_name="dynamodb")
    table = dynamo.Table(name=stack_params["TableName"])
    details_dict = DynamoModel(
        **dict(
            Client_ID=test_client,
            Password=test_pass,
            Username=test_user,
            allow_read=True,
            read_topic=f"{test_topic}/*",
            allow_connect=True,
            allow_write=True,
            write_topic=f"{test_topic}/write",
        )
    )
    table.put_item(Item=details_dict.dict())
    sleep(5)  # some pause to give things a chance to be readable
    yield details_dict
    # teardown delete item
    table.delete_item(Key=dict(Client_ID=test_client))


class StackParams(TypedDict):
    UnsignedAuthorizerName: str
    UnsignedAuthorizerStatus: bool
    TableName: str


@pytest.fixture(scope="session")
def stack_params() -> StackParams:
    stack = cloudformation_client.Stack(stack_name)
    return {x["OutputKey"]: x["OutputValue"] for x in stack.outputs}


def wait_for_event(event: bool, wait_time: int = 20):
    for i in range(wait_time):
        if event:
            return
        else:
            sleep(1)
