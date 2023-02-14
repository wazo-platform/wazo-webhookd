FROM wazoplatform/wazo-webhookd

ENV PYTHONDONTWRITEBYTECODE='true'

RUN apt-get -q update && apt-get -yq install --no-install-recommends procps

COPY . /usr/src/wazo-webhookd

WORKDIR /usr/src/wazo-webhookd
RUN python setup.py develop

WORKDIR /usr/src/wazo-webhookd/integration_tests/plugins/sentinel
RUN python setup.py develop

RUN cat /usr/src/wazo-webhookd/integration_tests/assets/ssl/mockserver/mockserver.crt >> /opt/venv/lib/python3.9/site-packages/certifi/cacert.pem
RUN cat /usr/src/wazo-webhookd/integration_tests/assets/fake-apple-ca/certs/server.crt >> /opt/venv/lib/python3.9/site-packages/certifi/cacert.pem

CMD ["wazo-webhookd", "-d"]
