#!/bin/bash

set -ex

test -n "$COGUARD_USER_NAME"
test -n "$COGUARD_PASSWORD"

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-image "$IMAGE_NAME") | sed 1,18d | tee "$TEMP_DIR/$IMAGE_NAME" | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    rm -rf "${TEMP_DIR:-?}/$IMAGE_NAME"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM";
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

# Docker image tests

test_image_checksum "nginx:1.23.2" "4b3323a5333bc0063f5b49904530eb7b6b072252"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "8a7b5ae7d69da636e4b12c7aefd9f6b376da22dd"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "8b1e1433a6ef1d79a40d39e87e94cc8cdefbaf60"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "e7a1526b6a5896c5d663140a3182cc6715836397"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "8526910fa23b027aaeeaecbc2a2c19096e9d8fb4"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "8e18871133667d2d58e634d9619607bc128dce52"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "87a1d6daba739fd65e06de46a3651fdb98188c48"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "7637aee8084c39d1c1675d0e7f0748e296e63c49"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "d10fa51c55b19b28c458a384b4b80e3f1471c04e"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "70a41abc1e136b6151458c9249ae4f1daf7f8b2e"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "3179369975c75e337f05c553281f5d5035cb1349"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 31b4c7c9b7a9a29fd9d8a3acaf25a4a53c449261
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 ed4a13cbc4fb4e29342cdac64d49d64d31b3efd6
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 3c092bdd8357c717e7966f608c62c97ec0cb78f4
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 2bc474fc32f4ff6cb0fb51bee6069f8a276fb98e
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 a0fa0659983a5639177c6e951aa3da535e64bd0f

rm -rf "$TEMP_DIR"
