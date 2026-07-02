ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.8
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY rootfs/app /app
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
