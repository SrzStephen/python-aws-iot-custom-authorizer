from typing import List, Literal, Optional

from pydantic import BaseModel, validator

iot_effect = Literal[
    "iot:Connect",
    "iot:GetRetainedMessage",
    "iot:ListRetainedMessages",
    "iot:Publish",
    "iot:Receive",
    "iot:RetainPublish",
    "iot:Subscribe",
    "iot:DeleteThingShadow",
    "iot:GetThingShadow",
    "iot:ListNamedShadowsForThing",
    "iot:UpdateThingShadow",
]


class PolicyStatement(BaseModel):
    Action: iot_effect
    Effect: Literal["Allow", "Deny"]
    Resource: str


class PolicyDocumentObject(BaseModel):
    Version: Literal["2012-10-17"] = "2012-10-17"
    Statement: List[PolicyStatement]


class PolicyDocument(BaseModel):
    password: Optional[str]
    isAuthenticated: bool
    principalId: str
    disconnectAfterInSeconds: int
    refreshAfterInSeconds: int
    policyDocuments: List[PolicyDocumentObject]


class DynamoModel(BaseModel):
    Client_ID: str
    Password: str
    Username: str
    read_topic: str
    write_topic: str
    allow_read: bool
    allow_connect: bool
    allow_write: bool


class ConnectionData(BaseModel):
    id: str


class MQTTData(BaseModel):
    username: str
    password: str  # I haven't bother putting an authorizer in but the creds come in via b64
    clientId: str


class TLSData(BaseModel):
    serverName: str


class ProtocolData(BaseModel):
    mqtt: MQTTData
    tls: Optional[TLSData]


class AuthorizerInput(BaseModel):
    # It's possible to create an authorizer with no token auth
    # AWS does not suggest this
    token: Optional[str]
    signatureVerified: Optional[bool]
    protocols: List[str]
    connectionMetadata: ConnectionData
    protocolData: ProtocolData

    # Doubt this'll cover up, but a list can be empty
    @validator("protocols")
    def is_expected_length(cls, v: List):
        if len(v) == 0:
            raise ValueError(f"Expected List of valid protocols, got {v}")

        for item in v:
            if item not in ["tls", "mqtt"]:  # Todo support https
                raise ValueError(f"got a value I didn't expect for protocol, {v}")
        return v
