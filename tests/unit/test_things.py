import os
from base64 import b64decode, b64encode, standard_b64decode, standard_b64encode
from copy import copy
from json import dumps, load, loads
from pathlib import Path
from uuid import uuid4

import boto3
import pytest
from cfn_tools import load_yaml
from moto import mock_dynamodb2
from mypy_boto3_dynamodb import DynamoDBServiceResource
from pydantic import ValidationError

from src.authorizer.authorizer.app import lambda_handler as lambda_dynamic
from src.authorizer.authorizer.types import AuthorizerInput, DynamoModel, PolicyDocument

root_path = Path(__file__).parent.parent.parent

event_path = root_path / "events"
from unittest import mock

TABLE_NAME_FOR_TESTING = "TestTablePleaseIgnore" + str(uuid4())
CLIENT_ID_FOR_TESTING = "CLIENT_NAME"
USERNAME_FOR_TESTING = "USER_NAME"
PASSWORD_FOR_TESTING = "PASS_WORD"
TOPIC_FOR_TESTING = "TestTopicPleaseIgnore" + str(uuid4())


def load_json(file_path: Path) -> dict:
    with open(file_path) as fp:
        return load(fp)


mqtt_auth = load_json(event_path / "mqtt_auth_no_verify.json")
mqtt_auth_verify = load_json(event_path / "mqtt_auth_verify.json")

input_data = [mqtt_auth, mqtt_auth_verify]  # so I can parameterize with a list


@pytest.mark.parametrize("data", input_data)
def test_types_parse(data: dict):
    AuthorizerInput(**data)


@pytest.mark.parametrize("data", input_data)
def test_fail_types(data: dict):
    # Check whether validate works the way I remember
    d1 = data.copy()
    d1["protocols"] = ["http"]
    with pytest.raises(ValidationError):
        AuthorizerInput(**d1)

    with pytest.raises(ValidationError):
        d2 = data.copy()
        d2["protocols"] = []
        AuthorizerInput.parse_obj(d2)


def load_table_from_yml() -> dict:
    yaml_path = root_path / "template.yaml"
    with open(yaml_path) as fp:
        yaml_doc = load_yaml(fp)
        table = yaml_doc["Resources"]["Table"]["Properties"]
        table["TableName"] = TABLE_NAME_FOR_TESTING
        return table


@mock_dynamodb2
def create_table_with_test_data():
    dynamo: DynamoDBServiceResource = boto3.resource(service_name="dynamodb")
    table = dynamo.create_table(**load_table_from_yml())

    table.put_item(
        Item=DynamoModel(
            **dict(
                Client_ID=CLIENT_ID_FOR_TESTING,
                Password=PASSWORD_FOR_TESTING,
                Username=USERNAME_FOR_TESTING,
                allow_read=True,
                read_topic=TOPIC_FOR_TESTING,
                allow_connect=True,
                allow_write=True,
                write_topic=TOPIC_FOR_TESTING,
            )
        ).dict()
    )
    assert table.scan()["Items"][0]["read_topic"] == TOPIC_FOR_TESTING
    return table


@mock_dynamodb2
def test_basic_gets():
    table = create_table_with_test_data()
    client_query = table.get_item(
        Key=dict(Client_ID=CLIENT_ID_FOR_TESTING),
        ProjectionExpression="Username, Password, read_topic",
    )
    assert client_query["Item"]["read_topic"] == TOPIC_FOR_TESTING


@pytest.mark.parametrize("data", input_data)
@mock.patch.dict(os.environ, dict(DYNAMO_TABLE_NAME=TABLE_NAME_FOR_TESTING))
@mock_dynamodb2
def test_handler_works(data: dict):
    good_input = copy(data)
    password = good_input["protocolData"]["mqtt"]["password"]
    good_input["protocolData"]["mqtt"]["password"] = b64encode(
        password.encode("utf-8")
    ).decode("utf-8")
    # test fn

    create_table_with_test_data()
    lambda_response = lambda_dynamic(good_input, None)
    assert lambda_response["isAuthenticated"] is True
    PolicyDocument(**lambda_response)  # Check that type matches


@mock.patch.dict(os.environ, dict(DYNAMO_TABLE_NAME=TABLE_NAME_FOR_TESTING))
@pytest.mark.parametrize("data", input_data)
@mock_dynamodb2
def test_password_doesnt_work(data):
    create_table_with_test_data()
    # Inject bad password into input data
    bad_input = copy(data)
    bad_input["protocolData"]["mqtt"]["password"] = b64encode(
        "BadPass".encode("utf-8")
    ).decode("utf-8")
    lambda_response = lambda_dynamic(data, None)

    assert lambda_response["isAuthenticated"] is False
    PolicyDocument(**lambda_response)  # Check that type matches


@mock.patch.dict(os.environ, dict(DYNAMO_TABLE_NAME=TABLE_NAME_FOR_TESTING))
@pytest.mark.parametrize("data", input_data)
@mock_dynamodb2
def test_missing_client_id(data):  # Shouldn't give an error
    create_table_with_test_data()
    bad_input = copy(data)
    bad_input["protocolData"]["mqtt"]["clientId"] = "BadClientId"
    # Inject bad password into input data
    lambda_response = lambda_dynamic(data, None)
    assert lambda_response["isAuthenticated"] is False
    PolicyDocument(**lambda_response)  # Check that type matches
