FROM wazopbx/wazo-webhookd

ENV PYTHONDONTWRITEBYTECODE='true'

COPY . /usr/src/wazo-webhookd

WORKDIR /usr/src/wazo-webhookd
RUN python setup.py develop

WORKDIR /usr/src/wazo-webhookd/integration_tests/plugins/sentinel
RUN python setup.py develop

RUN cat /usr/src/wazo-webhookd/integration_tests/assets/ssl/mockserver/mockserver.crt >> /usr/local/lib/python3.5/site-packages/certifi/cacert.pem

CMD ["wazo-webhookd", "-d"]
