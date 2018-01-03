.PHONY: test-setup test egg-info pull-images webhookd db

test-setup: egg-info pull-images webhookd db

test:
	nosetests -x

egg-info:
	cd .. && python setup.py egg_info
	cd plugins/sentinel && python setup.py egg_info

pull-images:
	docker pull n3llyb0y/wait
	docker pull swaggerapi/swagger-validator
	docker pull wazopbx/xivo-auth-mock
	docker pull jamesdbloom/mockserver:mockserver-5.2.3

webhookd:
	docker pull python:3.4.2
	docker build -t wazopbx/wazo-webhookd ..
	$(MAKE) webhookd-test

webhookd-test: egg-info
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..

db:
	docker build -f ../contribs/docker/Dockerfile-db -t wazopbx/wazo-webhookd-db ..
