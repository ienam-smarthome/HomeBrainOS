ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.8
FROM ${BUILD_FROM}

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY rootfs/app /app
RUN printf '%s' "${BUILD_VERSION}" > /app/.homebrain-build-version
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
