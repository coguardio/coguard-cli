#!/bin/bash

set -ex

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python -m coguard_cli docker-image "$IMAGE_NAME") | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
}

test_image_checksum "nginx:1.23.2" "c36b39ceb6249488c5a37cf960e6dfc90b23c53e"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "45e7560dad934bd3e0c66666b24d332d44680c58"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "fff513caf7a1805c8ee96b435c66f0378518160d"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "217adb8465ec142c8a4b31f70077d73034494b3d"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "c4fe5928e270c7c4b8e16231332854238cecaf99"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "8329648fb6e1200beca5c619ffeae96ce7d38c07"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "58abd637587c03c698ffa5230ddd063ebd0cf503"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "1fca8d731648d1795ebb081a8068f7ee650922a8"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "3c2a0b70d2ab1138d119b1e21847b1c6fe36aa04"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "dd74730402fdce6c3a88bdc0febbaddc75467879"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "dd4a2440a58ea901eecff892bec77b86d07fd96d"
docker image rm "amazon/aws-otel-collector:v0.22.1"
