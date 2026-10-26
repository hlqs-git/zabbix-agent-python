ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG PROFILE
COPY build-offline-container.sh /setup-prerequisites.sh
RUN PROFILE=${PROFILE} bash /setup-prerequisites.sh
