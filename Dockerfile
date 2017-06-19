FROM python:3.4.2

ADD . /usr/src/wazo-webhookd
ADD ./contribs/docker/certs /usr/share/xivo-certs

WORKDIR /usr/src/wazo-webhookd

RUN true \
    && adduser --quiet --system --group wazo-webhookd \
    && mkdir -p /etc/wazo-webhookd/conf.d \
    && install -o wazo-webhookd -g wazo-webhookd -d /var/run/wazo-webhookd \
    && touch /var/log/wazo-webhookd.log \
    && chown wazo-webhookd:wazo-webhookd /var/log/wazo-webhookd.log \
    && pip install -r requirements.txt \
    && python setup.py install \
    && cp -r etc/* /etc \
    && apt-get -yqq autoremove \
    && openssl req -x509 -newkey rsa:4096 -keyout /usr/share/xivo-certs/server.key -out /usr/share/xivo-certs/server.crt -nodes -config /usr/share/xivo-certs/openssl.cfg -days 3650

EXPOSE 9300

CMD ["wazo-webhookd"]
