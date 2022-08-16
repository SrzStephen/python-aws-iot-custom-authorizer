from json import dumps

import pytest
from awscrt.mqtt import Connection, QoS
from awsiot.mqtt_connection_builder import direct_with_custom_authorizer

from .test_helpers import (
    aws_endpoint,
    calltracker,
    generate_table,
    get_aws_ca_cert,
    stack_params,
    test_client,
    test_pass,
    test_topic,
    test_user,
    wait_for_event,
)


@pytest.fixture(scope="function")
def aws_iot_connection(
    get_aws_ca_cert: get_aws_ca_cert,
    stack_params: stack_params,
    generate_table: generate_table,
) -> Connection:
    return direct_with_custom_authorizer(
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


@calltracker
def aws_on_message(*args, **kwargs):
    pass


@pytest.mark.dependency()
def test_mqtt_connect(
    aws_iot_connection: aws_iot_connection, generate_table: generate_table
):
    connect_future = aws_iot_connection.connect()
    connect_future.result(timeout=20)  # will error if there's an issue


@pytest.mark.dependency(depends=["test_mqtt_connect"])
def test_mqtt_receive(
    aws_iot_connection: aws_iot_connection, generate_table: generate_table
):
    connect_future = aws_iot_connection.connect()
    connect_future.result(timeout=20)
    subscribe_future, packet = aws_iot_connection.subscribe(
        topic=f"{test_topic}/#",
        qos=QoS.AT_LEAST_ONCE,  # type: ignore
        callback=aws_on_message,
    )  # type: ignore
    subscribe_future.result(timeout=20)
    aws_iot_connection.publish(
        topic=f"{test_topic}/write",
        payload=dumps(dict(source="aws_sdk_v2_python")),
        qos=QoS.AT_LEAST_ONCE,
    )  # type: ignore
    wait_for_event(aws_on_message.has_been_called)  # type: ignore
    assert aws_on_message.has_been_called  # type: ignore
