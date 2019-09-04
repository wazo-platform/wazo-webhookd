.PHONY: test-setup test egg-info pull-images webhookd db

test-setup: egg-info pull-images webhookd db

test:
	nosetests -x

egg-info:
	cd .. && python setup.py egg_info
	cd plugins/sentinel && python setup.py egg_info

pull-images:
	# TODO(sileht:) wait for https://github.com/jamesdbloom/mockserver/pull/662 to be released
	# docker pull jamesdbloom/mockserver:mockserver-5.2.3
	docker pull sileht/mockserver
	docker pull wazopbx/wait
	docker pull wazopbx/wazo-auth-mock

webhookd:
	docker build -t wazopbx/wazo-webhookd ..
	$(MAKE) webhookd-test

webhookd-test: egg-info
	docker build --no-cache -t wazo-webhookd-test -f Dockerfile ..

db:
	docker build -f ../contribs/docker/Dockerfile-db -t wazopbx/wazo-webhookd-db ..
