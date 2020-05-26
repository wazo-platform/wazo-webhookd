FROM wazopbx/wazo-webhookd

ENV PYTHONDONTWRITEBYTECODE='true'

COPY . /usr/src/wazo-webhookd

WORKDIR /usr/src/wazo-webhookd
RUN python setup.py develop

WORKDIR /usr/src/wazo-webhookd/integration_tests/plugins/sentinel
RUN python setup.py develop

RUN cat /usr/src/wazo-webhookd/integration_tests/assets/ssl/mockserver/mockserver.crt >> /opt/venv/lib/python3.7/site-packages/certifi/cacert.pem
RUN cat /usr/src/wazo-webhookd/integration_tests/assets/fake-apple-ca/certs/server.crt >> /opt/venv/lib/python3.7/site-packages/certifi/cacert.pem

RUN apt-get -q update
RUN apt-get -yq install --no-install-recommends procps

CMD ["wazo-webhookd", "-d"]
