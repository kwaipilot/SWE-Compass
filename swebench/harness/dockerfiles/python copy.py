# _DOCKERFILE_BASE_PY = r"""


# ENV http_proxy="http://oversea-squid1.jp.txyun:11080" \
#     https_proxy="http://oversea-squid1.jp.txyun:11080" \
#     HTTP_PROXY="http://oversea-squid1.jp.txyun:11080" \
#     HTTPS_PROXY="http://oversea-squid1.jp.txyun:11080" \
#     no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com" \
#     NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"

# # 设置 pip 和 uv 的私有源
# ENV PIP_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/" \
#     UV_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/"

# FROM --platform={platform} ubuntu:{ubuntu_version}

# ARG DEBIAN_FRONTEND=noninteractive
# ENV TZ=Etc/UTC

# RUN apt update && apt install -y \
# wget \
# git \
# build-essential \
# libffi-dev \
# libtiff-dev \
# python3 \
# python3-pip \
# python-is-python3 \
# jq \
# curl \
# locales \
# locales-all \
# tzdata \
# && rm -rf /var/lib/apt/lists/*

# # Download and install conda
# RUN wget 'https://repo.anaconda.com/miniconda/Miniconda3-{conda_version}-Linux-{conda_arch}.sh' -O miniconda.sh \
#     && bash miniconda.sh -b -p /opt/miniconda3
# # Add conda to PATH
# ENV PATH=/opt/miniconda3/bin:$PATH
# # Add conda to shell startup scripts like .bashrc (DO NOT REMOVE THIS)
# RUN conda init --all
# RUN conda config --append channels conda-forge

# RUN adduser --disabled-password --gecos 'dog' nonroot
# """

# _DOCKERFILE_ENV_PY = r"""FROM --platform={platform} {base_image_key}

# COPY ./setup_env.sh /root/
# RUN sed -i -e 's/\r$//' /root/setup_env.sh
# RUN chmod +x /root/setup_env.sh
# RUN /bin/bash -c "source ~/.bashrc && /root/setup_env.sh"

# WORKDIR /testbed/

# # Automatically activate the testbed environment
# RUN echo "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed" > /root/.bashrc
# """

# _DOCKERFILE_INSTANCE_PY = r"""FROM --platform={platform} {env_image_name}

# COPY ./setup_repo.sh /root/
# RUN sed -i -e 's/\r$//' /root/setup_repo.sh
# RUN /bin/bash /root/setup_repo.sh

# WORKDIR /testbed/
# """
_DOCKERFILE_BASE_PY = r"""
FROM --platform={platform} ubuntu:{ubuntu_version}

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# set PROXY
# 设置系统级代理（影响 apt/wget/curl 等）
ENV http_proxy="http://oversea-squid1.jp.txyun:11080" \
    https_proxy="http://oversea-squid1.jp.txyun:11080" \
    HTTP_PROXY="http://oversea-squid1.jp.txyun:11080" \
    HTTPS_PROXY="http://oversea-squid1.jp.txyun:11080" \
    no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com" \
    NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"

# 设置 pip 和 uv 的私有源
ENV PIP_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/" \
    UV_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/"

# RUN apt update 

# RUN rm -f /var/lib/dpkg/lock* /var/cache/apt/archives/lock /etc/group.*lock*

# RUN apt install -y \
# wget \
# git \
# build-essential \
# libffi-dev \
# libtiff-dev \
# python3 \
# python3-pip \
# python-is-python3 \
# jq \
# curl \
# locales \
# locales-all \
# tzdata \
# && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    rm -f /var/lib/dpkg/lock* /var/cache/apt/archives/lock /etc/group.*lock* && \
    apt-get install -y --no-install-recommends \
    wget build-essential libffi-dev libtiff-dev \
    python3 python3-pip python-is-python3 jq curl \
    locales locales-all tzdata && \
    rm -rf /var/lib/apt/lists/*

# 单独安装 git，并跳过 openssh-client（可选）
RUN apt-get update && \
    apt-get install -y --no-install-recommends git || true

# Download and install conda
# RUN wget 'https://repo.anaconda.com/miniconda/Miniconda3-{conda_version}-Linux-{conda_arch}.sh' -O miniconda.sh \
#     && bash miniconda.sh -b -p /opt/miniconda3
RUN wget 'https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-{conda_version}-Linux-{conda_arch}.sh' -O miniconda.sh \
    && bash miniconda.sh -b -p /opt/miniconda3
# Add conda to PATH
ENV PATH=/opt/miniconda3/bin:$PATH
# Add conda to shell startup scripts like .bashrc (DO NOT REMOVE THIS)
RUN conda init --all
RUN conda config --append channels conda-forge

RUN adduser --disabled-password --gecos 'dog' nonroot
"""

_DOCKERFILE_ENV_PY = r"""FROM --platform={platform} {base_image_key}

# set PROXY
# 设置系统级代理（影响 apt/wget/curl 等）
ENV http_proxy="http://oversea-squid1.jp.txyun:11080" \
    https_proxy="http://oversea-squid1.jp.txyun:11080" \
    HTTP_PROXY="http://oversea-squid1.jp.txyun:11080" \
    HTTPS_PROXY="http://oversea-squid1.jp.txyun:11080" \
    no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com" \
    NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"

# 设置conda源
RUN conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/ && \
    conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/ && \
    conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/ && \
    conda config --set show_channel_urls yes

# 设置 pip 和 uv 的私有源
ENV PIP_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/" \
    UV_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/"


COPY ./setup_env.sh /root/
RUN sed -i -e 's/\r$//' /root/setup_env.sh
RUN chmod +x /root/setup_env.sh
RUN /bin/bash -c "source ~/.bashrc && /root/setup_env.sh"

WORKDIR /testbed/

# Automatically activate the testbed environment
RUN echo "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed" > /root/.bashrc
"""

_DOCKERFILE_INSTANCE_PY = r"""FROM --platform={platform} {env_image_name}

# set PROXY
# 设置系统级代理（影响 apt/wget/curl 等）
ENV http_proxy="http://oversea-squid1.jp.txyun:11080" \
    https_proxy="http://oversea-squid1.jp.txyun:11080" \
    HTTP_PROXY="http://oversea-squid1.jp.txyun:11080" \
    HTTPS_PROXY="http://oversea-squid1.jp.txyun:11080" \
    no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com" \
    NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"

# 设置conda源
RUN conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/ && \
    conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/ && \
    conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/ && \
    conda config --set show_channel_urls yes

# 设置 pip 和 uv 的私有源
ENV PIP_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/" \
    UV_INDEX_URL="https://pypi.corp.kuaishou.com/kuaishou/prod/+simple/"

COPY ./setup_repo.sh /root/
RUN sed -i -e 's/\r$//' /root/setup_repo.sh
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
"""
