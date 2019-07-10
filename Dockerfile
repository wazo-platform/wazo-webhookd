FROM python:3.5-debian

ADD . /usr/src/wazo-webhookd
ADD ./contribs/docker/certs /usr/share/xivo-certs

WORKDIR /usr/src/wazo-webhookd

# NOTE(sileht): As we pin all versions on debian, we can just create a base
# image with all python deps of wazo-plateform. This will reduce a lot
# the times gate take to run
RUN true \
    && adduser --quiet --system --group wazo-webhookd \
    && mkdir -p /etc/wazo-webhookd/conf.d \
    && install -o wazo-webhookd -g wazo-webhookd -d /var/run/wazo-webhookd \
    && touch /var/log/wazo-webhookd.log \
    && chown wazo-webhookd:wazo-webhookd /var/log/wazo-webhookd.log \
    && pip install --no-cache-dir -c constraint-debian.txt -c constraint-tarballs.txt . \
    && cp -r etc/* /etc \
    && apt-get -yqq autoremove \
    && openssl req -x509 -newkey rsa:4096 -keyout /usr/share/xivo-certs/server.key -out /usr/share/xivo-certs/server.crt -nodes -config /usr/share/xivo-certs/openssl.cfg -days 3650 \
    && chown wazo-webhookd:wazo-webhookd /usr/share/xivo-certs/*

EXPOSE 9300

CMD ["wazo-webhookd"]
