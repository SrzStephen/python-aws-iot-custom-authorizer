# Arduino connect
This demo is built using [PlatformIO](https://platformio.org/install).

This is a C++ example using [PubSubClient](https://pubsubclient.knolleary.net/) for a fairly minimal amount of
code required to connect to AWS IOT with an IOT Custom Authorizer (without signature verification) via MQTT,
along with publishing a message to make sure that it works.


## Setup
There are a set of variables that you will need to set in `secrets.h` before this example will work.

These variables should be pretty obvious if you've 
[read through the README in the python-aws-iot-custom-authorizer](https://github.com/SrzStephen/python-aws-iot-custom-authorizer)

```c
const char* wifi_name = "";
const char* wifi_pass = "";
const char* mqtt_username = "";
const char* mqtt_password = "";
const char* mqtt_client_id = "";
const char* mqtt_ats_endpoint = "";
const char* mqtt_custom_authorizer_name= "";
const char* mqtt_publish_topic = "";
```

For convenience the [AWS ECC 256 bit CA3 Key](https://docs.aws.amazon.com/iot/latest/developerguide/server-authentication.html) 
has already been included since it's not a secret.

# Issues
AWS suggests that the `x-amz-customauthorizer-name` gets URL encoded. I haven't got around to implementing this.
I haven't implemented this but i'd expect if you start having spaces in your authorizer name then you'd have an issue.

There is currently no support for signature verification, in theory this should be pretty easy (add it to 
`mqtt_modified_username`) as suggested by AWS in their [connection guide](https://docs.aws.amazon.com/iot/latest/developerguide/custom-auth.html#custom-auth-mqtt)