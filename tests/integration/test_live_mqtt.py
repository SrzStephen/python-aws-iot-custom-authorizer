import ssl
import urllib.request
from datetime import datetime
from json import loads
from os import getenv
from pathlib import Path
from time import sleep
from typing import Generator, TypedDict
from urllib import parse as url_parse
from uuid import uuid4

import boto3
import functools
import paho.mqtt.client as mqtt
import pytest
from awscrt.mqtt import QoS, Connection
from awsiot.mqtt_connection_builder import direct_with_custom_authorizer
from mypy_boto3_cloudformation import CloudFormationServiceResource
from mypy_boto3_dynamodb import DynamoDBServiceResource
from mypy_boto3_iot import IoTClient
from mypy_boto3_iot.type_defs import MqttContextTypeDef

from src.authorizer.authorizer.types import DynamoModel

stack_name = getenv("STACK_NAME", "authorizer")
iot_client: IoTClient = boto3.client("iot")
cloudformation_client: CloudFormationServiceResource = boto3.resource("cloudformation")
time_format = datetime.now().strftime("%m%d%Y%H%M")
aws_endpoint = iot_client.describe_endpoint(endpointType="iot:Data-ATS")[
    "endpointAddress"
]


def calltracker(func):
    # from https://dzone.com/articles/python-how-to-tell-if-a-function-has-been-called
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.has_been_called = True
        return func(*args, **kwargs)

    wrapper.has_been_called = False
    return wrapper


@calltracker
def function_1_calltracker():
    pass


@calltracker
def function_2_caltracker():
    pass


def test_calltracker():
    function_1_calltracker()
    assert function_1_calltracker.has_been_called
    assert function_2_caltracker.has_been_called is False
    function_2_caltracker()
    assert function_2_caltracker.has_been_called


def uuid_partial() -> str:
    return str(uuid4()).replace("-", "")


def get_val() -> str:
    return f"int{time_format}"


test_user = get_val() + uuid_partial()
test_pass = get_val() + uuid_partial()
test_client = get_val() + uuid_partial()
test_topic = f"integration/{uuid_partial()}".replace("-", "")


class StackParams(TypedDict):
    UnsignedAuthorizerName: str
    UnsignedAuthorizerStatus: bool
    TableName: str


@pytest.fixture(scope="session")
def stack_params() -> StackParams:
    stack = cloudformation_client.Stack(stack_name)
    return {x["OutputKey"]: x["OutputValue"] for x in stack.outputs}


@pytest.fixture(scope="session")
def generate_table(stack_params) -> Generator[None, None, None]:
    dynamo: DynamoDBServiceResource = boto3.resource(service_name="dynamodb")
    table = dynamo.Table(name=stack_params["TableName"])
    table.put_item(
        Item=DynamoModel(
            **dict(
                Client_ID=test_client,
                Password=test_pass,
                Username=test_user,
                allow_read=True,
                read_topic=f"{test_topic}/read",
                allow_connect=True,
                allow_write=True,
                write_topic=f"{test_topic}/write",
            )
        ).dict()
    )
    sleep(10)
    yield None
    # teardown delete item
    table.delete_item(Key=dict(Client_ID=test_client))


def test_unsigned_invalid(stack_params):
    # This is a sanity check to make sure that the authorizer actually works, we don't care about the values
    if stack_params["UnsignedAuthorizerStatus"]:
        response = iot_client.test_invoke_authorizer(
            authorizerName=stack_params["UnsignedAuthorizerName"],
            mqttContext=MqttContextTypeDef(
                username=str(uuid4()), password=str(uuid4()), clientId=str(uuid4())
            ),
        )
        assert response["isAuthenticated"] is False


def test_unsigned_valid(stack_params, generate_table):
    if stack_params["UnsignedAuthorizerStatus"]:
        response = iot_client.test_invoke_authorizer(
            authorizerName=stack_params["UnsignedAuthorizerName"],
            mqttContext=MqttContextTypeDef(
                username=test_user, password=test_pass, clientId=test_client
            ),
        )
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        assert response["isAuthenticated"] is True
        policy_doc = loads(response["policyDocuments"][0])
        assert len(policy_doc["Statement"]) > 0


@pytest.fixture(scope="session")
def get_aws_ca_cert() -> Path:
    aws_ca = Path(__file__).parent / "awsCA.pem"
    urllib.request.urlretrieve(
        "https://www.amazontrust.com/repository/AmazonRootCA1.pem", aws_ca.absolute()
    )
    yield aws_ca
    # teardown
    aws_ca.unlink()


@pytest.fixture(scope="function")
def paho_client(get_aws_ca_cert, generate_table, stack_params) -> mqtt.Client:
    # Note this will do TLS auth
    def username_and_auth(username: str) -> str:
        # https://docs.aws.amazon.com/iot/latest/developerguide/config-custom-auth.html
        # If you're doing signature you'll need to set this too
        return f"{username}?x-amz-customauthorizer-name={url_parse.quote_plus(stack_params['UnsignedAuthorizerName'])}"

    mqtt_client = mqtt.Client(client_id=test_client)
    # Add in ALPN and support AWS CA
    ssl_context = ssl.create_default_context()
    ssl_context.set_alpn_protocols(["mqtt"])
    ssl_context.load_verify_locations(get_aws_ca_cert)
    mqtt_client.tls_set_context(context=ssl_context)
    mqtt_client.username_pw_set(
        username=username_and_auth(test_user), password=test_pass
    )
    return mqtt_client


@calltracker
def paho_on_connect(*args, **kwargs):
    pass


@calltracker
def paho_on_publish(client, userdata, mid):
    pass


@calltracker
def paho_on_receive(**kwargs):
    pass


def test_paho_connect(stack_params, generate_table, paho_client):
    # paho_client.on_connect = paho_on_connect
    paho_client.connect(host=aws_endpoint, port=443, keepalive=60)
    paho_client.loop_start()
    sleep(20)
    paho_client.publish(
        topic=f"/{test_topic}/write",
        payload=dict(message="Connected with Paho").__str__(),
    )
    assert paho_on_connect.has_been_called


def test_paho_write(stack_params, generate_table, paho_client):
    paho_client.on_publish = paho_on_publish
    paho_client.connect(host=aws_endpoint, port=443, keepalive=60)
    paho_client.loop_start()
    sleep(20)
    paho_client.publish(
        topic=f"/{test_topic}/write",
        payload=dict(message="Connected with Paho").__str__(),
    )
    assert paho_on_publish.has_been_called


@pytest.fixture(scope="function")
def aws_iot_connection(get_aws_ca_cert) -> Connection:
    pass


def test_mqtt_client(stack_params, generate_table, get_aws_ca_cert):
    conn = direct_with_custom_authorizer(
        auth_username=test_user,
        auth_authorizer_name=stack_params["UnsignedAuthorizerName"],
        auth_password=test_pass,
        **dict(
            endpoint=aws_endpoint,
            client_id=test_client,
            ca_filepath=get_aws_ca_cert.absolute().__str__(),
            port=443,
        ),
    )
    connect_future = conn.connect()
    connect_future.result(timeout=20)  # will error if there's an issue
    conn.publish(
        f"/{test_topic}/write",
        payload=dict(message="Connected with aws iot core").__str__(),
        qos=QoS(0),
    )
