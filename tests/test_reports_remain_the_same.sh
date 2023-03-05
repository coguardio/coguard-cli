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
    rm -rf "${TEMP_DIR:-?}/$IMAGE_NAME"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python -m coguard_cli folder "${TEMP_DIR:-?}"/tmp_repo_dir) | tee "$TEMP_DIR/folder_check.txt" | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM";
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

# Docker image tests

test_image_checksum "nginx:1.23.2" "5609ecabe882db34bb5289c9f2247b7d26e04317"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "a705e1098b0c80f01245ede1f28ca50f1ffa53e1"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "60edd380ed66af9de73ede2cbb3cdb6709700aa2"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "66a4a86216b943583115999c71d0ca6efffcafa7"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "fce461515b759275258c1f0c2b374d3a52144568"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "1a397f87f4b1003801c40d499a655f0e631764e0"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "3b2c2ae37e6039c7140ba5f69092bb9a0121dc6d"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "652befcf31fd74713af9f5b29ecd27dfe108dba7"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "0c780f7503d5d44739073910dbf15d38e1a6c7d3"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "770ca2a7ceea8ad78c51be4e2531bc546f0d077e"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "360bf2d7e25e7e36185927568c13b8ec9d220e64"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df e55b6da66af6ab99a3763ddde2e85030290c7a6e
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 57bc3dd5c81e20d04586e1c8b061e41f9f428cf5
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 300d39e308b550caaa0d8597592b0d385b37b126
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 52d38b49a6673addf432d3a9b86ca18e83346a72
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 66c847b61daf597967d00a4c5bacbec587511d82

rm -rf "$TEMP_DIR"
