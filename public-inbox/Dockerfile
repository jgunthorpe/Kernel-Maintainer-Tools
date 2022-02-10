# docker build public-inbox/ -t lei
FROM ubuntu:focal
RUN apt-get -qq update -y && apt-get -qq upgrade
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    libdbd-sqlite3-perl \
    libdbi-perl \
    libemail-address-xs-perl \
    libemail-mime-perl \
    libencode-perl \
    libgit2-dev \
    libinline-c-perl \
    libio-compress-perl \
    liblinux-inotify2-perl \
    libmail-imapclient-perl \
    libnet-server-perl \
    libparse-recdescent-perl \
    libplack-middleware-reverseproxy-perl \
    libplack-perl \
    libsearch-xapian-perl \
    libtimedate-perl \
    liburi-perl \
    make \
    pkg-config \
    sqlite3 \
    xapian-tools

RUN mkdir -p /opt/ && \
    git -C /opt/ clone https://public-inbox.org/public-inbox.git && \
    git -C /opt/public-inbox/ reset --hard 303c3507b4aefc0e08d792de02357ea9ab0fc322

RUN mkdir -p /root/.cache/public-inbox/inline-c/

RUN cd /opt/public-inbox && \
    perl Makefile.PL && \
    make && \
    make install

# RUN make test
