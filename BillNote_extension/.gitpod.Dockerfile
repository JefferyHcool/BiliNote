FROM gitpod/workspace-full-vnc

USER root

# Install dependencies
RUN apt-get update                                            \
    && apt-get install -y firefox
