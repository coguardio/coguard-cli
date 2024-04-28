#!/bin/bash

set -ex

test -n "$COGUARD_USER_NAME"
test -n "$COGUARD_PASSWORD"

IS_TEST=${1:-false};

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-image "$IMAGE_NAME") | sed 1,18d | tee "$TEMP_DIR/$IMAGE_NAME" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    fi
    rm -rf "${TEMP_DIR:-?}/$IMAGE_NAME"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    fi
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

test_folder_fix() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir --fix=true)
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

# Docker image tests

test_image_checksum "nginx:1.23.2" "b08152374d9176bc1024fbdad58837dffa2f6eba"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "ab23c1f34b955ee1b429fdf098330e9cdd8dde01"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "f84dc697ccb23b461ca73d6c3c66e16a752e8f2c"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "1d17447a44031c3089757f65ff0f6f1fedc7501b"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "0e7de7ba6d0a0e1987d3f294e69fb2417010da8d"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "7057f8255fd6a5aa816616f7a2735414fa88b286"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "d2ddfba54a0124ce1a9715aa58b0aae8a533b842"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "e49b6bdeb704dea67b0463e1f0cb69fedd211446"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "8cedfc2a60e88ec68de37beb23585a50072c9036"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "d453c36a8193119b33993c5d4562145a95b86bb3"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "6297c55a86bfe6420f02d6841a0e7edc96690703"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df d676866edb65abf08a2e9e9bb801b493a75424d7
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 c29ce769c6abb381fdf683b31466de9df8f3ef3b
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 3d5d7c59480a2c361e644f4a7665dcfb1f00e2c3
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 ec585c4919be57ce690889106e473f55d8fc7721
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 7adf1f439662c5f433044a63b63462e88149bb86
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

rm -rf "$TEMP_DIR"
