test-setup: egg-info webhookd webhookd-test db

test:
	pytest -x

egg-info:
	cd .. && python setup.py egg_info
	cd plugins/sentinel && python setup.py egg_info

webhookd:
	docker build -t wazoplatform/wazo-webhookd ..

webhookd-test: egg-info
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..

db:
	docker build -f ../contribs/docker/Dockerfile-db -t wazoplatform/wazo-webhookd-db ..

.PHONY: test-setup test egg-info webhookd webhookd-test db
