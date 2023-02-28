# wazo-webhookd

[![Build Status](https://jenkins.wazo.community/buildStatus/icon?job=wazo-webhookd)](https://jenkins.wazo.community/job/wazo-webhookd)

A microservice to manage and trigger webhooks in the [Wazo PBX](https://wazo-platform.org).


wazo-webhookd allow the administrator to manage webhooks (incoming or outgoing)
using a simple HTTP interface.


## Docker

The official docker image for this service is `wazoplatform/wazo-webhookd`.


### Getting the image

To download the latest image from the docker hub

```sh
docker pull wazoplatform/wazo-webhookd
```


### Running wazo-webhookd

```sh
docker run -e"XIVO_UUID=<the wazo UUID>" wazoplatform/wazo-webhookd
```

### Building the image

Building the docker image:

```sh
docker build -t wazoplatform/wazo-webhookd .
```
