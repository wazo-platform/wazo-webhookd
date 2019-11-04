.PHONY: test-setup test egg-info pull-images webhookd db

test-setup: egg-info pull-images webhookd db

test:
	nosetests -x

egg-info:
	cd .. && python setup.py egg_info
	cd plugins/sentinel && python setup.py egg_info

pull-images:
	docker pull jamesdbloom/mockserver:mockserver-5.7.0
	docker pull wazopbx/wait
	docker pull wazopbx/wazo-auth-mock
	docker pull nginx

webhookd:
	docker build -t wazopbx/wazo-webhookd ..
	$(MAKE) webhookd-test

webhookd-test: egg-info
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..

db:
	docker build -f ../contribs/docker/Dockerfile-db -t wazopbx/wazo-webhookd-db ..
