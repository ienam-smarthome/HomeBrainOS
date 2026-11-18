ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.8
FROM ${BUILD_FROM}

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3 py3-pip tzdata
WORKDIR /app
COPY rootfs/app /app
COPY tools/first_answer_audit.py tools/source_real_acceptance.py /app/
ENV HOMEBRAIN_PACKAGE_VERSION="${BUILD_VERSION}"
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt
RUN python3 -c 'from source_real_acceptance import ALPHA145_PACK, init_labels, verify'
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
