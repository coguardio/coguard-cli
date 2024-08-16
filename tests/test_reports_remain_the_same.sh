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
test_image_checksum "mysql:8.0.31" "330900d7eea98defee5cf6b95f8ce1529143b84c"
test_image_checksum "mysql:8.0.31" "7579e5f990d40998e8d3e6e01efa6db48914c74e" stig
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "4fa159437ff236e7cf2195a53e213e2f17f7b5d5"
test_image_checksum "postgres:15.1" "8eca512bc7ff7816419f4c55a594eedbe88a8869" soc2
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "11573dd2bb16683135ca303bb029ee0b1b1ae4a1"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "bcbfc4b159c089a0210a8a243b9a2563cf8cfd7f"
test_image_checksum "mariadb:10.9.4" "08e7a31efba48555bcddcf1b8c261d5aefebaf17" hipaa
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
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "4bcb120d187847367f84def039a09f7c28976900"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 07620788b8adbc96a57bc167675594dd97dccb8c
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 c6c03b05b87f3a35d0ecbf54fc92072a71602dca
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 0c9bcdcc012cd11230f193c5ce26df5cfb5d4dad
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 3fda8b6305219dd54d8e735078dad95b30d554a7
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 7adf1f439662c5f433044a63b63462e88149bb86
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

rm -rf "$TEMP_DIR"
