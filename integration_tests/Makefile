.PHONY: test pull-images webhookd db

test-setup: pull-images webhookd db

test:
	pytest -x

pull-images:
	docker pull jamesdbloom/mockserver:mockserver-5.2.3
	docker pull wazopbx/wait
	docker pull wazopbx/wazo-auth-mock

webhookd:
	docker build --pull -t wazopbx/wazo-webhookd ..
	$(MAKE) webhookd-test

webhookd-test:
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..

db:
	docker build -f ../contribs/docker/Dockerfile-db -t wazopbx/wazo-webhookd-db ..
