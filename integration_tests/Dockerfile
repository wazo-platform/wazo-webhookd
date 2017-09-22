FROM wazopbx/wazo-webhookd

ENV PYTHONDONTWRITEBYTECODE='disabled'

COPY . /usr/src/wazo-webhookd

WORKDIR /usr/src/wazo-webhookd
RUN python setup.py develop

WORKDIR /usr/src/wazo-webhookd/integration_tests/plugins/sentinel
RUN python setup.py develop

CMD ["wazo-webhookd", "-d"]
