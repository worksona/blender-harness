# Blender harness: headless Blender + Claude Code on Ubuntu 24.04 (x86_64).
# Runs anywhere Docker does: a cloud VM, a devcontainer, GitHub Codespaces.
#
#   docker compose build
#   docker compose run --rm --service-ports harness           # shell
#   docker compose run --rm --service-ports harness claude    # Claude Code
FROM ubuntu:24.04

ARG BLENDER_VERSION=5.2.2
ENV DEBIAN_FRONTEND=noninteractive \
    BLENDER_VERSION=${BLENDER_VERSION} \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils git make python3 python3-venv less ripgrep sudo \
      libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 \
      libgl1 libegl1 \
    && rm -rf /var/lib/apt/lists/* \
    && echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu

COPY scripts/setup.sh /tmp/setup.sh
RUN bash /tmp/setup.sh && rm /tmp/setup.sh && blender --version | head -1

USER ubuntu
ENV PATH=/home/ubuntu/.local/bin:$PATH
RUN curl -fsSL https://claude.ai/install.sh | bash && claude --version

WORKDIR /workspace
EXPOSE 8000
CMD ["bash"]
