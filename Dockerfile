FROM python:3.10-bullseye as base

RUN apt update && apt install -y git openssh-client curl bash coreutils
RUN apt install -y \
curl bash ca-certificates openssl coreutils  \
pngcrush optipng make gcc g++ \
grep util-linux binutils findutils \
&& rm -rf /var/lib/apt/lists/*

RUN mkdir -p ~/.ssh && ssh-keyscan -t rsa github.com >> ~/.ssh/known_hosts

ENV PYTHONUNBUFFERED 1
ENV GIT_SSH_COMMAND ssh

COPY requirements.txt /opt/app/requirements.txt
RUN pip install --no-cache-dir -r /opt/app/requirements.txt
ADD . /opt/app
WORKDIR /opt/app

ENV PYTHONPATH="${PYTHONPATH}:."
EXPOSE 8000
RUN chmod +x *.sh
CMD ["bash", "run.sh"]
