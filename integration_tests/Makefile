.PHONY: test-setup build-webhookd test pull-images

test-setup: pull-images build-webhookd

test:
	nosetests -x

egg-info:
	cd .. && python setup.py egg_info

pull-images:
	docker pull n3llyb0y/wait
	docker pull swaggerapi/swagger-validator

build-webhookd:
	docker pull python:3.4.2
	docker build -t wazopbx/wazo-webhookd ..
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..
