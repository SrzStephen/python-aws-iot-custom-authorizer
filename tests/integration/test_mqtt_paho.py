import ssl
from time import sleep
from urllib import parse as url_parse

import paho.mqtt.client as mqtt
import pytest

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
def paho_client(
    get_aws_ca_cert: get_aws_ca_cert,
    generate_table: generate_table,
    stack_params: stack_params,
) -> mqtt.Client:
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
def paho_on_subscribe(*args, **kwargs):
    pass


@calltracker
def paho_on_message(*args, **kwargs):
    pass


@pytest.mark.dependency(depends=["test_unsigned_valid"])
def test_paho_connect(
    stack_params: stack_params, generate_table: generate_table, paho_client: paho_client
):
    paho_client.on_connect = paho_on_connect
    paho_client.connect(host=aws_endpoint, port=443, keepalive=60)
    paho_client.loop_start()
    wait_for_event(paho_on_connect.has_been_called)  # type: ignore
    paho_client.loop_stop()
    assert paho_on_connect.has_been_called  # type: ignore


@pytest.mark.dependency(depends=["test_paho_connect"])
def test_paho_write(
    stack_params: stack_params, generate_table: generate_table, paho_client: paho_client
):
    paho_client.on_publish = paho_on_publish
    paho_client.connect(host=aws_endpoint, port=443, keepalive=60)
    paho_client.loop_start()
    paho_client.publish(
        topic=f"{test_topic}/write",
        payload=dict(message="Connected with Paho").__str__(),
    )
    wait_for_event(paho_on_publish.has_been_called)  # type: ignore
    paho_client.loop_stop()
    assert paho_on_publish.has_been_called  # type: ignore


@pytest.mark.dependency(depends=["test_paho_connect", "test_paho_write"])
def test_paho_subscribe(
    stack_params: stack_params, generate_table: generate_table, paho_client: paho_client
):
    paho_client.on_subscribe = paho_on_subscribe
    paho_client.on_message = paho_on_message
    paho_client.connect(host=aws_endpoint, port=443, keepalive=60)
    sleep(5)
    paho_client.subscribe(f"{test_topic}/#")
    paho_client.loop_start()
    paho_client.publish(
        topic=f"{test_topic}/write",
        payload=dict(message="Connected with Paho").__str__(),
    )
    wait_for_event(
        all([paho_on_subscribe.has_been_called, paho_on_message.has_been_called])
    )
    paho_client.loop_stop()
    assert paho_on_subscribe.has_been_called  # type: ignore
    assert paho_on_message.has_been_called  # type: ignore
