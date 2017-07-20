# wazo-webhookd

[![Build Status](https://travis-ci.org/wazo-pbx/wazo-webhookd.svg?branch=master)](https://travis-ci.org/wazo-pbx/wazo-webhookd)

A micro service to manage plugins in the [Wazo PBX](http://wazo.community).


wazo-webhookd allow the administrator to manage webhooks (incoming or outgoing)
using a simple HTTP interface.


## Docker

The official docker image for this service is `wazopbx/wazo-webhookd`.


### Getting the image

To download the latest image from the docker hub

```sh
docker pull wazopbx/wazo-webhookd
```


### Running wazo-webhookd

```sh
docker run -e"XIVO_UUID=<the wazo UUID>" wazopbx/wazo-webhookd
```

### Building the image

Building the docker image:

```sh
docker build -t wazopbx/wazo-webhookd .
```
