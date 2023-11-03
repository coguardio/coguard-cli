#!/bin/bash

set -x

test -n "$COGUARD_USER_NAME"
test -n "$COGUARD_PASSWORD"

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-image "$IMAGE_NAME") | sed 1,18d | tee "$TEMP_DIR/$IMAGE_NAME" | sort | sha1sum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    rm -rf "${TEMP_DIR:-?}/$IMAGE_NAME"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM";
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

# Docker image tests

test_image_checksum "nginx:1.23.2" "9e0feaad74d6f67088f37d64b0cb16ee3fc4ab81"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "d5a8a531da1040529d5b94857487037ac238e3d6"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "a95f304c2d6832d21c540acd0b86890bf60e5748"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "fcebe9746c89d679947bcb731c33defd348e65c1"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "bbded79ab7977392228e666ec3bb0e43740b30a8"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "1d1a6188d413b25eb67bdc54de7d67a1114a4084"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "da59d6fb2ed70ac1250e08bb6e6e972dd8ed6761"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "866e3c573f92b0dec18ee8ea29239bf097480e20"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "315a17e5bad8c975ca75083c6936817007bc54be"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "59343e46bfc353ed046f9d3d713306850aff6d0e"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "70a41abc1e136b6151458c9249ae4f1daf7f8b2e"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df fd4f279401567036cb33409fa54461ec27250f07
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 0276abbd77fc62a8724f35297fe11c693a9fa787
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 57bb47c00ab976ad8b0a861bf60bd69fc51810ac
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 7a586c64e27db4b334d3735914cb96e081cbd192
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 5fa75bfaab5f5adec5863ec18844fcef96b77e8a

rm -rf "$TEMP_DIR"
