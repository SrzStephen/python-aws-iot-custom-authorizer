# Lambda Authorizer


## Motivation
There are a few cases where not using the default certificate based authentication in AWS IOT is beneficial for example [TASMOTA](https://tasmota.github.io/docs/AWS-IoT/#1-prerequisites)

I also wanted to get a hang of seeing what testing AWS resources on github actions would be like

## About
The documentation on Custom Authorizers 


## What Next
Right now one of the limitations is tha I haven't implemented Token Signing yet
> If you leave signing enabled, you can prevent excessive triggering of your Lambda by unrecognized clients. Consider this before you disable signing in your authorizer.

When I get around to that I will add it as a new export in the Cloudformation template and use a 
parameter `  UnsignedAuthorizerStatus` to decide whether this is enabled or disabled.