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

test_image_checksum "nginx:1.23.2" "69bc757a21d0a81fe92b9e93b11a8e9750e5e008"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "828ae648a07f79dad8d60ee18a7c7cab50e11435"
test_image_checksum "mysql:8.0.31" "ce01757c73ab5d0d85b4f30e9807f25a9820dd04" stig
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "4fa159437ff236e7cf2195a53e213e2f17f7b5d5"
test_image_checksum "postgres:15.1" "8eca512bc7ff7816419f4c55a594eedbe88a8869" soc2
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "11573dd2bb16683135ca303bb029ee0b1b1ae4a1"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "b2622095704ae7080ce70f05918e1f0b96c03aef"
test_image_checksum "mariadb:10.9.4" "75b53c4345d21af9022e0ce109dcaeb3d9e9a935" hipaa
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "4b5aecbe74d0fbd6a68c68e832747e44e3a66768"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "16b03fffb98474b2f7ba2fbbf07e7868eb7a6749"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "15fdb4ff7d4e8cdfddd18eeb73dbdb84dc99e003"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "d15dcf7d045acbf0de181104ac3dcfe6006d1342"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "80d3e29fc531047a40430194b6df1f0451db1fbc"
docker image rm "redis:7.0.5"
test_image_checksum "rethinkdb:2.4.4-bookworm-slim" "f5bdf596877e210e89cefb5b63dc79d19a4855d0"
docker image rm "rethinkdb:2.4.4-bookworm-slim"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "08a49d0a5a38a6fafc723bcb73fb459bbc6ca61a"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 68a28bc8a650749881f94e9e0487137ee9fde5c6
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 4e6f5cfd3b251452a10e757312645ccaefd145d7
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 ae7e5931f2e0d22bc6eaec42b4139e9af8e9ade5
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 98087a874a6c5039a103ac818c1f9402ef8c599f
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 67081c91818a12d1572bd06cb9bd63e79015cc8d
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

rm -rf "$TEMP_DIR"
