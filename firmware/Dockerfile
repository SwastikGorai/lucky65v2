FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git patch rsync bzip2 xz-utils ccache \
    libusb-1.0-0 libhidapi-hidraw0 libhidapi-libusb0 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fL --retry 5 -o /tmp/arm.tar.bz2 \
    https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2 \
    && echo '97dbb4f019ad1650b732faffcc881689cedc14e2b7ee863d390e0a41ef16c9a3  /tmp/arm.tar.bz2' | sha256sum -c - \
    && tar -xjf /tmp/arm.tar.bz2 -C /opt && rm /tmp/arm.tar.bz2
ENV PATH="/opt/gcc-arm-none-eabi-10.3-2021.10/bin:${PATH}"
COPY --from=ghcr.io/astral-sh/uv:0.9.15 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/qmk-venv UV_PYTHON_DOWNLOADS=never
ENV PATH="/opt/qmk-venv/bin:${PATH}"
COPY pyproject.toml uv.lock /recipe/firmware/
RUN uv sync --project /recipe/firmware --locked --no-dev --no-install-project --python /usr/local/bin/python3
COPY setup.sh /recipe/firmware/setup.sh
COPY patches /recipe/firmware/patches
RUN QMK_TREE=/opt/qmk bash /recipe/firmware/setup.sh \
    && find /recipe -type f -print0 | sort -z | xargs -0 sha256sum > /opt/build-environment.txt \
    && arm-none-eabi-gcc --version >> /opt/build-environment.txt \
    && uv --version >> /opt/build-environment.txt
WORKDIR /src
CMD ["bash", "/src/firmware/build.sh"]
