from json import loads
from uuid import uuid4

import pytest
from mypy_boto3_iot.type_defs import MqttContextTypeDef

from .test_helpers import (
    generate_table,
    iot_client,
    stack_params,
    test_client,
    test_pass,
    test_user,
)


def test_unsigned_invalid(stack_params: stack_params):
    # This is a sanity check to make sure that the authorizer actually works, we don't care about the values
    if stack_params["UnsignedAuthorizerStatus"]:
        response = iot_client.test_invoke_authorizer(
            authorizerName=stack_params["UnsignedAuthorizerName"],
            mqttContext=MqttContextTypeDef(
                username=str(uuid4()), password=str(uuid4()), clientId=str(uuid4())
            ),
        )
        assert response["isAuthenticated"] is False


@pytest.mark_dependency()
def test_unsigned_valid(stack_params: stack_params, generate_table: generate_table):
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
