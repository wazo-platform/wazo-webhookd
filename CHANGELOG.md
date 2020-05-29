# Changelog

## 20.08

* Deprecate SSL configuration

## 18.12

* The body of endpoint `GET /status` has been added a new subkey `status`.


## 18.01

* New attribute for subscriptions:

  * `metadata`

* The following resources accept a new `search_metadata` query parameter:

  * GET `/1.0/subscriptions`
  * GET `/1.0/users/me/subscriptions`


## 17.14

* New resources to manage webhooks as a user:

  * GET `/1.0/users/me/subscriptions`
  * POST `/1.0/users/me/subscriptions`
  * GET `/1.0/users/me/subscriptions/<uuid>`
  * PUT `/1.0/users/me/subscriptions/<uuid>`
  * DELETE `/1.0/users/me/subscriptions/<uuid>`

* New options for subscriptions:

  * `events_wazo_uuid`

* New default value for config options for subscriptions with service `http`:

  * `body` defaults to the JSON-encoded form of `event[data]`. When the default value is used, `content-type` is set to `application/json`.


## 17.13

* New options for subscriptions:

  * `events_user_uuid`


## 17.12

* New config options for subscriptions with service `http`:

  * `verify_certificate`
  * `content_type`

* The config option `body` for subscriptions with service `http` now accept template values.
* A new API for checking the status of the daemon:

  * GET `/1.0/status`

* A new API for getting the available services:

  * GET `/1.0/subscriptions/services`

## 17.11

* New resources to manage webhook subscriptions

  * GET `/1.0/subscriptions`
  * POST `/1.0/subscriptions`
  * GET `/1.0/subscriptions/<uuid>`
  * PUT `/1.0/subscriptions/<uuid>`
  * DELETE `/1.0/subscriptions/<uuid>`


## 17.09

* A new resource has been added to fetch the current configuration of wazo-webhookd
