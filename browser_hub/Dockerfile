FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    SCREEN_WIDTH=1440 \
    SCREEN_HEIGHT=900 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get -o Acquire::ForceIPv4=true update && \
    apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends \
        chromium \
        fonts-noto-cjk \
        xvfb \
        fluxbox \
        x11vnc \
        novnc \
        websockify \
        socat \
        tini \
        curl \
        procps \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
        fastapi \
        "uvicorn[standard]" \
        playwright

RUN apt-get -o Acquire::ForceIPv4=true update && \
    apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends libatomic1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY entrypoint.sh /app/entrypoint.sh
COPY server.py /app/server.py
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /data/profile /root/.fluxbox && \
    printf "session.screen0.toolbar.visible: false\n" > /root/.fluxbox/init

EXPOSE 6080 8090

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
