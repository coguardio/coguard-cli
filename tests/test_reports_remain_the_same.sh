#!/bin/bash

set -ex

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python -m coguard_cli docker-image "$IMAGE_NAME") | tee "$TEMP_DIR/$IMAGE_NAME" | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    rm -rf "$TEMP_DIR/$IMAGE_NAME"
}

test_image_checksum "nginx:1.23.2" "d63dcf82420a60dd1c597aad4058bfa0662fbedc"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "fd19a65b5383397fb7eceaca5e74e57485871219"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "2e1e8a00ae91815ea550f005eab7f0bb2f770a82"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "1aa4e334f467b7e98235d261c206912933029629"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "321c080916065e83711bcdc2ef84fcbdfe22135b"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "169103b12dc13211ef842328eaeb72148d03fa7b"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "95f89f79109766cddf25dd78c4d5934a27efee04"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "ae0789d0cb0ac5e34afbd96c29d03ed6ff68022d"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "b471fdabd17b6e3a5d506164e0268f66796f1ecd"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "fc0b023dddb78ce448f13b04b970fd6f0f5db985"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "1532d7ffa2fecd8da58ab495b3b50e77bf868059"
docker image rm "amazon/aws-otel-collector:v0.22.1"

rm -rf "$TEMP_DIR"
