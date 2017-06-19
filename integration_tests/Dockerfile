FROM wazopbx/wazo-webhookd

COPY . /usr/src/wazo-webhookd
WORKDIR /usr/src/wazo-webhookd

ENV PYTHONDONTWRITEBYTECODE='disabled'

RUN python setup.py develop

CMD ["wazo-webhookd", "-d"]
