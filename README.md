# Lambda Authorizer

## Motivation

AWS normally needs you to use x509 certificate based authentication to connect to AWS IOT. This is the more secure
way and is probably strongly recomended.

However, it can be a bit of pain when you're trying to wire things
like [Tasmota](https://tasmota.github.io/docs/AWS-IoT/#1-prerequisites)
up to AWS IOT or for cases where you have IOT devices where you don't really need to worry about maintaining Things or
device shadows.

For these cases, you can use username and password authentication (Along with the AWS Certificate Authority) by creating
a Custom Authorizer to handle the authentication side for you.

### Custom Authorizer

An AWS Custom Authorizer is a lambda function that gets a message like this

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

And has to implement the decisions of

* Should this device be authorized to connect
* What IOT policies should it have.

### Implementation

I chose a drop dead simple to maintain design.

Essentially, the lambda function will look at the `clientId` and find an appropriate username and password for
that client, if the username and password are authenticated, then it moves on to figure out whether the device
should have a policy to connect `can_connect`, as well as whether it `can_write` to a topic and whether it `can_read`
from a topic.

## What Next

### Token signing

Right now one of the limitations is tha I haven't implemented Token Signing yet
> If you leave signing enabled, you can prevent excessive triggering of your Lambda by unrecognized clients. Consider
> this before you disable signing in your authorizer.

When I get around to that I will add it as a new export in the Cloudformation template and use a
parameter `  UnsignedAuthorizerStatus` to decide whether this is enabled or disabled.

### HTTP support

I currently don't have this wired up to do authorizations with http clients. Currently I don't have a need although
pull requests are welcome.

### Demo with Arduino (ESP32)

Part of the reason for this is to help me quickly spin up IOT projects, so I plan to get an Esp32 demo in there.

### Github Actions integration

I've got some decent testing so it shouldn't be hard to have a proper staging and prod environment with CI that
auto rolls back on failure.

## Testing

### Unit testing

The unit testing simply runs a set of known good events and makes sure they work.
The testing makes heavy use of the `moto` library to make mocking dynamodb calls and inserting fake data a breeze

### Integration testing

To finish wiring up.

The integration testing currently has `aws-iot-sdk` and `paho` examples for connecting and writing messages

The integration testing calls the test invoke lambda to make sure that the authorizer is capable of working as expected.