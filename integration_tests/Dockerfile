FROM wazoplatform/wazo-webhookd

ENV PYTHONDONTWRITEBYTECODE='true'

RUN apt-get -q update && apt-get -yq install --no-install-recommends procps

COPY . /usr/src/wazo-webhookd

WORKDIR /usr/src/wazo-webhookd
RUN python3 -m pip install -e .

WORKDIR /usr/src/wazo-webhookd/integration_tests/plugins/sentinel
RUN python3 -m pip install -e .

RUN cat /usr/src/wazo-webhookd/integration_tests/assets/ssl/mockserver/mockserver.crt >> /opt/venv/lib/python3.11/site-packages/certifi/cacert.pem
RUN cat /usr/src/wazo-webhookd/integration_tests/assets/fake-apple-ca/certs/server.crt >> /opt/venv/lib/python3.11/site-packages/certifi/cacert.pem

CMD ["wazo-webhookd", "-d"]
