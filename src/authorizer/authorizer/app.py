from base64 import b64decode
from datetime import datetime, timedelta
from os import environ
from typing import List, Optional, Tuple
from uuid import uuid4

from boto3 import resource as boto_resource
from cachetools import TTLCache, cached
from mypy_boto3_dynamodb import ServiceResource
from mypy_boto3_dynamodb.service_resource import Table

from .types import (
    AuthorizerInput,
    DynamoModel,
    MQTTData,
    PolicyDocument,
    PolicyStatement,
)

cache = TTLCache(ttl=timedelta(minutes=5), maxsize=1024 * 1000 * 5, timer=datetime.now)

# Defaults but easily overridable
DISCONNECT_SECONDS = int(
    environ.get("DISCONNECT_SECONDS", timedelta(hours=1).total_seconds())
)
REFRESH_SECONDS = int(
    environ.get("REFRESH_SECONDS", timedelta(hours=1).total_seconds())
)


@cached(cache)
def get_resources() -> Tuple[ServiceResource, Table]:
    client: ServiceResource = boto_resource(service_name="dynamodb")
    table = client.Table(environ.get("DYNAMO_TABLE_NAME", None))
    return client, table


def check_password(db_creds: DynamoModel, request_creds: MQTTData) -> bool:
    # Note, password comes in as base64 under normal circumstances
    return all(
        [
            db_creds.Username == request_creds.username,
            db_creds.Password == b64decode(request_creds.password).decode("utf-8"),
        ]
    )


def get_details_for_client_id(client_id: str, table: Table) -> DynamoModel:
    return DynamoModel(
        **table.get_item(
            Key=dict(Client_ID=client_id),
            ProjectionExpression="Username, Password, AllowedTopic, allow_read, "
            "allow_connect, allow_write, read_topic, write_topic",
        )["Item"],
        Client_ID=client_id,
    )


def generate_policy(
    dynamoData: Optional[DynamoModel], authenticated: bool, client_id: str
) -> PolicyDocument:
    def format_principal(s: str) -> str:
        # Member must satisfy ([a-zA-Z0-9]){1,128}
        truncate = s[0:120] if len(s) > 120 else s
        return "".join(i for i in f"{truncate}:{uuid4()}" if i.isalnum())

    # AWS region is a default env so I dont need to worry about setting it
    base_iot_string = f"arn:aws:iot:{environ.get('AWS_REGION', None)}:{environ.get('AWS_ACCOUNT_ID', None)}"
    policy_statements: List[PolicyStatement] = []
    print(f"client authentication {client_id}: {authenticated}")
    if authenticated:  # Only create allow policies if the client is authenticated
        if dynamoData.allow_connect:
            policy_statements.append(
                PolicyStatement(
                    **dict(
                        Action="iot:Connect",
                        Effect="Allow",
                        Resource=f"{base_iot_string}:client/{dynamoData.Client_ID}",
                    )
                )
            )
        if dynamoData.allow_read:
            policy_statements.append(
                PolicyStatement(
                    **dict(
                        Action="iot:Subscribe",
                        Effect="Allow",
                        Resource=f"{base_iot_string}:topicfilter/{dynamoData.read_topic}",
                    )
                )
            )
            policy_statements.append(
                PolicyStatement(
                    **dict(
                        Action="iot:Receive",
                        Effect="Allow",
                        Resource=f"{base_iot_string}:topic/{dynamoData.read_topic}",
                    )
                )
            )
        if dynamoData.allow_write:
            policy_statements.append(
                PolicyStatement(
                    **dict(
                        Action="iot:Publish",
                        Effect="Allow",
                        Resource=f"{base_iot_string}:topic/{dynamoData.write_topic}",
                    )
                )
            )

    return PolicyDocument(
        **dict(
            password=None
            if authenticated is False or dynamoData is None
            else dynamoData.Password,
            isAuthenticated=authenticated,
            # principal Id
            principalId=format_principal(client_id),
            disconnectAfterInSeconds=DISCONNECT_SECONDS,
            refreshAfterInSeconds=REFRESH_SECONDS,
            policyDocuments=[dict(Version="2012-10-17", Statement=policy_statements)],
        )
    )


def lambda_handler(event, context):
    input_val = AuthorizerInput(**event)
    details = input_val.protocolData.mqtt
    # you're probably sending the auth header through, it's not actually part of the username
    details.username = details.username.split("?x-amz-customauthorizer-name")[0]

    if environ.get("REQUIRE_SIGNATURE_VERIFICATION", False):
        if not input_val.signatureVerified:
            generate_policy(
                authenticated=False, dynamoData=None, client_id=details.clientId
            ).dict()
    client, table = get_resources()
    try:
        data = get_details_for_client_id(details.clientId, table)
    except KeyError:  # User ID not found in table
        return generate_policy(
            authenticated=False, dynamoData=None, client_id=details.clientId
        ).dict()
    returned_policy = generate_policy(
        dynamoData=data,
        authenticated=check_password(data, details),
        client_id=details.clientId,
    ).dict()
    print(returned_policy)
    return returned_policy
