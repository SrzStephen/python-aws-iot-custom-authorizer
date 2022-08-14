# Lambda Authorizer

[![.github/workflows/basic_test.yml](https://github.com/SrzStephen/python-aws-iot-custom-authorizer/actions/workflows/basic_test.yml/badge.svg?branch=main)](https://github.com/SrzStephen/python-aws-iot-custom-authorizer/actions/workflows/basic_test.yml)
[![.github/workflows/arduino_test.yml](https://github.com/SrzStephen/python-aws-iot-custom-authorizer/actions/workflows/arduino_test.yml/badge.svg)](https://github.com/SrzStephen/python-aws-iot-custom-authorizer/actions/workflows/arduino_test.yml)

## Motivation

AWS normally needs you to
use [x509 certificate based authentication](https://docs.aws.amazon.com/iot/latest/developerguide/x509-client-certs.html)
to connect to AWS IOT. This certificate based Authention can be a bit of a pain when it comes to things that expect
Username/Password authentication like [Tasmota](https://tasmota.github.io/docs/AWS-IoT/#1-prerequisites), or cases
where you don't really want some of the advanced AWS IOT features and realistically just want something for your IOT
devices to pubsub to.

In these cases you can use
an [AWS Custom Authorizer](https://docs.aws.amazon.com/iot/latest/developerguide/custom-authentication.html)
to handle the authentication side of things for you.

## Documentation

I found that the documentation for how to create and use the custom authorizer was a bit lacking, particularly because
there are a few gotchas when it comes
to [MQTT authentication](https://docs.aws.amazon.com/iot/latest/developerguide/custom-auth.html),
and it seems like some of the stackoverflow questions are no longer relevent due to things like ATS endpoint changes.

## Usage

Install [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html),
[AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
and deploy the SAM template with

```zsh
sam build
sam deploy --guided
````

I would then suggest running the test suite in `tests/integration` to make sure that your deployment worked properly.
You will probably need to set an environment variable `STACK_NAME` for the name of the stack so that the integration
tests can find the resources that it needs to run its tests.

Once you've verified that all this works, you'll probably want to insert some credentials into your DynamoDB table/


Get your table name from the output of the stack you just deployed

```zsh
aws cloudformation describe-stacks --stack-name STACK_NAME-HERE
```

Insert your credentials into dynamodb to be used by the authenticator,
either [via the console or CLI](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/getting-started-step-2.html)
. This example uses the CLI.

```zsh
aws dynamodb execute-statement --statement "INSERT INTO TALBENAME_FROM_PREVIOUS \
Value \
{'Client_ID':'TestClientID','Password':'TestPasswordChangeme','Username':'TestUserChangeMe', 
'allow_read': true, 'allow_write':true,'allow_connect':true,'read_topic':'testopic/read',
'write_topic':'testtopic/write'}"
```

You're probably going to need your `ATS` IOT endpoint to know what to connect to (this is the only endpoint supported).

```zsh
aws iot describe-endpoint --endpoint-type "iot:Data-ATS"
```

### Connection

#### Python

I've included tests in [tests/integration/test_live_mqtt](tests/integration/test_live_mqtt.py) which should clear up how
clients can connect via python
(using `paho` and the `aws-iot` libraries) to show how to connect with Python.

#### Arduino (C++)

There is also a basic PlatformIO project in [arduino_connect_example](arduino_connect_example) which demos a working
example to connect with Arduino (C++) via [PubSubClient](https://pubsubclient.knolleary.net/). This example has a few
variables that need to be filled in, so it's worth reading that examples [readme](arduino_connect_example/README.md).

## Custom Authorizer

The AWS IOT Custom Authorizer recieves credentials sent by the MQTT client on connection.

```json
{
  "protocolData": {
    "mqtt": {
      "username": "USER_NAME",
      "password": "PASS_WORD",
      "clientId": "CLIENT_NAME"
    }
  },
  "protocols": [
    "mqtt"
  ],
  "signatureVerified": false,
  "connectionMetadata": {
    "id": "d0adaaa7-b22d-4545-923c-68a7ae2e337c"
  }
}
```

The Authorizer (Lambda) then has the job of figuring out whether a device should be authorized to connect, and what
IOT policies it should have.

For my usage, this is generally permissions to connect and read/write to a specified topic/topic filter.

```json
{
  "isAuthenticated": true,
  "password": "PasswordHere",
  "principalId": "PrincipalHere",
  "disconnectAfterInSeconds": 3600,
  "refreshAfterInSeconds": 3600,
  "policyDocuments": [
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": "iot:Connect",
          "Effect": "Allow",
          "Resource": "arn:aws:iot:ap-southeast-2:MY_ID:client/CLIENT_ID"
        },
        {
          "Action": "iot:Receive",
          "Effect": "Allow",
          "Resource": "arn:aws:iot:ap-southeast-2:MY_ID:topic/integration/cbb38fe8/read"
        },
        {
          "Action": "iot:Subscribe",
          "Effect": "Allow",
          "Resource": "arn:aws:iot:ap-southeast-2:MY_ID:topicfilter/integration/cbb38fe8/read"
        },
        {
          "Action": "iot:Publish",
          "Effect": "Allow",
          "Resource": "arn:aws:iot:ap-southeast-2:MY_ID:topic/integration/cbb38fe8/write"
        }
      ]
    }
  ]
}
```

## Implementation

I wanted a simple serverless solution to maintain and design because I'm kind of lazy.

![Authorizer](docs/authorizer_example.png)

The Lambda function acting as the authorizer will look for the attributes associated with the key for the `Client_ID`,
out of those attributes it will get a `Username` and `password` to figure out whether the credentials that it's using
are valid, and will also retireve a set of attributes `can_write` `write_topic` `can_read` `read_topic` `can_connect`
for use in generating the IAM policy document for permissions that get passed to AWS IOT Core.

This allows a serverless way to provision new devices (Add a new Client_ID and attributes) to the DynamoDB table,
and by using [MQTT wildcards](https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/) in the
`read_topic` and `write_topic` it allows you to properly namespace your topics.

## Testing

### Unit testing

The unit testing uses a set of known good events to make sure that the lambda function works as intended before being
deployed to AWS. The testing makes heavy use of the `moto` library to make mocking dynamodb calls and inserting fake
data for testing purposes as easy as possible.

### Integration testing

The integration testing calls the `test-invoke-lambda-authorizer` to ensure that the authorizer works as expected as
far as being set up, and whether it provides the right response (Including whether the Policy Document is correctly
formed).

The integration testing also has two basic tests for the `aws-iot-sdk` and `paho` clients to ensure that a device
can properly connect without the abstraction layer provided by `test-invoke-lambda-authorizer`. This also serves as
documentation for how to connect using the custom authorizer.

## What Next

### Token signing

Right now one of the limitations is tha I haven't implemented Token Signing yet, from the AWS page:
> If you leave signing enabled, you can prevent excessive triggering of your Lambda by unrecognized clients. Consider
> this before you disable signing in your authorizer.

I'll eventually get around to adding this as a new export in the Cloudformation and use `UnsignedAuthorizerStatus` to
control whether the Unsigned Authorizer is enabled/disabled.

### HTTP support

I've set up the custom authorizer for MQTT authentication, but it also supports HTTP. This is a pretty simple addition
to the authorizer lambda, but I don't have a need for it yet, so it's a #TODO for later.

### Full CICD pipeline

I've written unit and integration tests which shouldn't be hard to wire into a proper CICD platform, at this point
however, I've just put in the `unit` tests into github actions.

The #Todo on finishing this off is creating an IAM deployment role with minimal permissions and
an IAM role for deployment. I've started this process on the `CICD` branch, it's not a priority for me
right now.

### Script for inserting new entries into dynamodb

THE CLI command to add a new entry to the table is a bit clunky, eventually I'll get around to setting up a
[click](https://click.palletsprojects.com/en/8.1.x/) CLI to make it a bit easier.