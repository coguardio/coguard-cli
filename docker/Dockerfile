FROM python:3.11.4-alpine3.18

ARG COGUARD_VERSION

RUN apk add docker=25.0.3-r0

#coguard-config-checker: disable dockerfile_shell_check_on_run_commands Minor necessary violations like the missing of shebang

# Creating a separate user
RUN addgroup -S coguard
RUN adduser -S coguard -G coguard
RUN addgroup coguard docker

ENV SCAN_FOLDER /opt/folder
RUN mkdir "$SCAN_FOLDER"
RUN chown -R coguard:coguard /opt/folder
COPY ./entrypoint.sh /home/coguard/entrypoint.sh
RUN chmod +x /home/coguard/entrypoint.sh

USER coguard

RUN pip install coguard-cli=="$COGUARD_VERSION"

VOLUME /var/log

#coguard-config-checker: disable dockerfile_env_and_arg_defined_and_right_away_used This is just PATH update
ENV PATH=${PATH}:/home/coguard/.local/bin

HEALTHCHECK CMD coguard -v

ENTRYPOINT /home/coguard/entrypoint.sh
