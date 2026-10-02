FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip make gcc-arm-none-eabi libnewlib-arm-none-eabi binutils-arm-none-eabi \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /bench
COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt
COPY . .
CMD ["./run_all.sh"]
