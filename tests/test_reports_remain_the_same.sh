#!/bin/bash

set -ex

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python -m coguard_cli docker-image "$IMAGE_NAME") | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
}

test_image_checksum "nginx:1.23.2" "1b82ef42c1686c57229abc3308069fcd7148db68"
test_image_checksum "mysql:8.0.31" "be2584e6aba996fb4c660070b14e8085fcc128d7"
test_image_checksum "postgres:15.1" "22dff0be80484b909a15af13453f6d7b5d6f2b03"
test_image_checksum "mongo:6.0.2" "7640626081683649c25d71bd17b7f0dcdd991191"
test_image_checksum "mariadb:10.9.4" "cc67faf237f3e7298d0ad327710bf28a0f7da3ae"
test_image_checksum "bitnami/kafka:3.3.1" "368b57bacbdcfac1fee5ad4354c171648386ba49"
test_image_checksum "httpd:2.4.54" "6f739c45751f49350a165f9b9369aa2097e64238"
test_image_checksum "elasticsearch:8.5.0" "22b8605b09a982335f18eaeb5bb5b151d0c68d95"
test_image_checksum "tomcat:9.0.69-jre17" "6ab8bcea46778a2f74a4d17c307623ad57bc2124"
test_image_checksum "redis:7.0.5" "c07e7a4133fe03f4ed046dc19656ea638efe940c"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "c37cc4f52720c0ad34b606ff8720e94dc352bc87"
