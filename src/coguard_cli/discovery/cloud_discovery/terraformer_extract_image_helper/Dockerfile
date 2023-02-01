FROM centos:8

# The container running from this image will expect the following
# environment variables to be set:
# - REGIONS (A comma separated list of different regions for the
#            specific provider)
# - AWS_ACCESS_KEY_ID (The AWS access key id for an account with
#                      sufficient read priviledges)
# - AWS_SECRET_ACCESS_KEY (The secret access key for AWS)
# - COGUARD_USERNAME (The username to authenticate to CoGuard)
# - COGUARD_PASSWORD (The password to authenticate to CoGuard)

#coguard-config-checker: disable dockerfile_container_healthcheck_parameter Not a continuously running service

ARG USER_ID=1000
ARG GROUP_ID=1000

# Creating a separate user
RUN groupadd -g "$GROUP_ID" terraformerUser
RUN useradd -u "$USER_ID" -g terraformerUser -s /bin/bash terraformerUser

# INSTALL Terraform
RUN cd /etc/yum.repos.d/
RUN sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-*
RUN sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*
RUN yum install -y yum-utils-4.0.21-3.el8
RUN yum-config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
RUN yum -y install terraform-1.2.9-1
RUN yum -y install jq-1.5-12.el8

# Install Terraformer

ENV CURRENT_TERRAFORMER_VERSION=0.8.21
# For now, we assume the provider to be AWS only; we would need to
# check for adjustments for other providers, and maybe need to create
# extra Docker files for that.
ENV PROVIDER=aws
RUN curl -LO "https://github.com/GoogleCloudPlatform/terraformer/releases/download/$CURRENT_TERRAFORMER_VERSION/terraformer-${PROVIDER}-linux-amd64"
RUN chmod +x terraformer-${PROVIDER}-linux-amd64
RUN mv terraformer-${PROVIDER}-linux-amd64 /usr/local/bin/terraformer

ENV TERRAFORMER_EXPORT_DATA=/opt/terraformer_export_data

RUN mkdir -p "$TERRAFORMER_EXPORT_DATA"
RUN mkdir -p /opt/tmp
COPY data/versions.tf /opt/tmp

VOLUME /var/log

RUN mkdir -p /home/terraformerUser/.aws

RUN chown -R terraformerUser:terraformerUser /opt/tmp "$TERRAFORMER_EXPORT_DATA"
RUN chown -R terraformerUser:terraformerUser /home/terraformerUser/.aws

COPY scripts/cmd_for_dfile /usr/bin/
RUN chmod a+x /usr/bin/cmd_for_dfile

USER terraformerUser

WORKDIR "$TERRAFORMER_EXPORT_DATA"

CMD /usr/bin/cmd_for_dfile