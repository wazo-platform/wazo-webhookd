FROM wazopbx/wazo-webhookd
ENV PYTHONDONTWRITEBYTECODE='true'
RUN pip install -e /usr/src/wazo-webhookd/integration_tests/plugins/sentinel
CMD ["wazo-webhookd", "-d"]
