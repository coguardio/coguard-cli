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

test_container_checksum() {
    CONTAINER_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    COMPLIANCE=${3:-""}
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --ruleset="$COMPLIANCE" --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-container "$CONTAINER_NAME") | sed 1,18d | tee "$TEMP_DIR/container_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        if [ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]
        then
            echo "ACTUAL checksum matched EXPECTED checksum for $CONTAINER_NAME";
        else
            echo "ACTUAL: $ACTUAL_CHECKSUM";
            echo "EXPECTED: $EXPECTED_CHECKSUM";
            echo "ACTUAL OUTPUT:";
            cat "$TEMP_DIR/container_check.txt";
            exit 1;
        fi
    fi
    rm -rf "${TEMP_DIR:-?}/container_check.txt"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    COMPLIANCE=${4:-""}
    EXTERNAL_SCAN_RESULTS=${5:-""}
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --ruleset="$COMPLIANCE" --additional-scan-result="$EXTERNAL_SCAN_RESULTS" --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}' );
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

time test_image_checksum "nginx:1.23.2" "18117f00e2d81fc214bd6a9020932d24cf3a47a6"
time docker image rm "nginx:1.23.2"
time test_image_checksum "mysql:8.0.31" "c736e8532a709eda8324f9374d0318862a733b0d"
time test_image_checksum "mysql:8.0.31" "9033734e8f63cc6fc39b5ea9c5e3f1c6ce6fe32f" stig
time docker image rm "mysql:8.0.31"
time test_image_checksum "postgres:15.1" "be855ac9c322fe1085d65df7878403f58c3d034d"
time test_image_checksum "postgres:15.1" "7838a4ec2dedf30eb5951d29473b95b9fc722394" soc2
time docker image rm "postgres:15.1"
time test_image_checksum "mongo:6.0.2" "5fef05856d385ba92f8ea223383b99e682d03fc2"
time docker image rm "mongo:6.0.2"
time test_image_checksum "mariadb:10.9.4" "f95e6591b09610a75f50e3967f7c7abf1525dd71"
time test_image_checksum "mariadb:10.9.4" "797845ab3a1b74f0ae38fbd63c02ac41613024e9" hipaa
time test_image_checksum "mariadb:10.9.4" "a6d375e07bfa0d16b2b02e6eee7323bc218bc570" nist800-53
time test_image_checksum "mariadb:10.9.4" "7292bb041c90962ccfe737ea2b8c18cf3686c894" fedramp
time test_image_checksum "mariadb:10.9.4" "2af133f8352ab118f5a96fb2e447dd545110723e" iso27001
time docker image rm "mariadb:10.9.4"
time test_image_checksum "bitnamilegacy/kafka:3.3.1" "a17511e39d71c202412a1118588b3e4819f5ca5d"
time docker image rm "bitnamilegacy/kafka:3.3.1"
time test_image_checksum "httpd:2.4.54" "6db5cf33e439ae9bc0fe7205501c13f2efc97f8b"
time docker image rm "httpd:2.4.54"
time test_image_checksum "elasticsearch:8.5.0" "96b704bc7492995fab8a1834af68cf9d97b5438d"
time docker image rm "elasticsearch:8.5.0"
time test_image_checksum "tomcat:9.0.69-jre17" "af93b8cc268f1a0e22b5438da3e40ed7a805b925"
time docker image rm "tomcat:9.0.69-jre17"
time test_image_checksum "redis:7.0.5" "fe13e5d82996adfe8728a79ebd2df098c14ffcf9"
time docker image rm "redis:7.0.5"
time test_image_checksum "rethinkdb:2.4.4-bookworm-slim" "c8dd0bf5cf40ca0dbe48604d3ab81aa4fa36d0ec"
time docker image rm "rethinkdb:2.4.4-bookworm-slim"
time test_image_checksum "amazon/aws-otel-collector:v0.22.1" "58ed7564f64973d9da9c02e1f62f831c462f56ab"
time docker image rm "amazon/aws-otel-collector:v0.22.1"
time
# Docker container tests
time docker run --rm -d -e POSTGRES_PASSWORD=foo --name=demo-postgres postgres:15.1
time test_container_checksum demo-postgres "b8865f36a96d93378ef0e8fe44953040ee0e60e7"
time docker stop demo-postgres

# Git repository tests

time test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 20d681fa865190cab59fad652952e21cf24bcd9a
time test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 6870903ffbaeac8f6ee004614f5c3170dfd3899b "" trivy_cve_scan
time test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 f9b52882df586ea828c230285c773bd005ea7d7e
time test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 89cfb1d435b276c308cbed275dbf38f76fca1544
time test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 a61ace3dd693cbe4e3408f943b2d94770df88f2f
time test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 4dbf1a5ebeeb397660d1bd57a2b694a938561d69
time test_folder_checksum https://github.com/yiisoft/yii2.git 778d708c4f028c6997ff42ee2e1aead86cce3a64 f68aeaed13248c1ccd2541dcf39a5d36330beadd "" phpstan_sast_scan
time test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

# Test with a weird name
time git clone https://github.com/ethereum/remix-project.git "$TEMP_DIR"/"tmp_repo_dir (1)";
time (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/"tmp_repo_dir (1)") | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}'

time rm -rf "$TEMP_DIR"
