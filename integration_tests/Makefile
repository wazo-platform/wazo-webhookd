test-setup: egg-info webhookd webhookd-test db

test:
	pytest -x

egg-info:
	cd .. && python setup.py egg_info
	cd plugins/sentinel && python setup.py egg_info

webhookd:
	docker build --pull -t wazoplatform/wazo-webhookd ..

webhookd-test: webhookd egg-info
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..

db:
	docker build -f ../contribs/docker/Dockerfile-db -t wazoplatform/wazo-webhookd-db:local ..

.PHONY: test-setup test egg-info webhookd webhookd-test db
