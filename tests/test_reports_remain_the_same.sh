#!/bin/bash

set -e

test -n "$COGUARD_USER_NAME"
test -n "$COGUARD_PASSWORD"

IS_TEST=${1:-false};

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    COMPLIANCE=${3:-""}
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --ruleset="$COMPLIANCE" --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-image "$IMAGE_NAME") | sed 1,18d | tee "$TEMP_DIR/image_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        if [ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]
        then
            echo "ACTUAL checksum matched EXPECTED checksum for $IMAGE_NAME";
        else
            echo "ACTUAL: $ACTUAL_CHECKSUM";
            echo "EXPECTED: $EXPECTED_CHECKSUM";
            echo "ACTUAL OUTPUT:";
            cat "$TEMP_DIR/image_check.txt";
            exit 1;
        fi
    fi
    rm -rf "${TEMP_DIR:-?}/image_check.txt"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    COMPLIANCE=${4:-""}
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --ruleset="$COMPLIANCE" --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        if [ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]
        then
            echo "ACTUAL checksum matched EXPECTED checksum for $GIT_REPO";
        else
            echo "ACTUAL: $ACTUAL_CHECKSUM";
            echo "EXPECTED: $EXPECTED_CHECKSUM";
            echo "ACTUAL OUTPUT:";
            cat "$TEMP_DIR/folder_check.txt";
            exit 1;
        fi
    fi
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
    rm -rf "$TEMP_DIR/folder_check.txt";
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

test_image_checksum "nginx:1.23.2" "ca532b2cc57393c82504333a5dad1c947afa83be"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "15f9d4d4a0c1356ad22260793c97789825ecc00d"
test_image_checksum "mysql:8.0.31" "ffd0dfbf8d5a12436cef8639fdbb587fc989afcd" stig
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "87eb693e99e9cdd60f5f8d79cea4d75fa2675ed9"
test_image_checksum "postgres:15.1" "f4333d5bc08540be3b17ce7c9430a4fef78437ab" soc2
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "be2d4a8ee7c83dbd04a896f44fd6ac5f33b69913"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "1498f771142810f494930da77234a0b6c5b59e6b"
test_image_checksum "mariadb:10.9.4" "54318b75d6fc2f7ec948fdb64d63c82ff0ff20b4" hipaa
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "9dae7d5bfc8d9f9002e3fc670c941092c4c14f56"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "774139309ef3ff82f40f5c31a2b6e7493da5ea07"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "54d3970c4ac30423e9e92beb2356246adddb0246"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "712d6a7502e64cb9baa00e0571cb20c89ebf4c3b"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "32ebbd865d23088b802ea5adee2b068734f9d6ca"
docker image rm "redis:7.0.5"
test_image_checksum "rethinkdb:2.4.4-bookworm-slim" "728e5bff42a891911520e394a04a11f05439159a"
docker image rm "rethinkdb:2.4.4-bookworm-slim"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "9253ac064181113f972856a7f304fb7cc9d21ae6"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df cff2be9fa9933ecdbf05fbac3b6530d0364e68c0
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 0867ade8961470de6dadb31e88bf7b3c381a0c05
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 6f7ef1a03ae3c0234580a3cbc7ca672f54bd959c
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 665ccf1f9c8a3f17c6f85646db6a3868014ad195
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 d5eeca2c63c658fb9fc3df6f096658b14b00a737
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

rm -rf "$TEMP_DIR"
