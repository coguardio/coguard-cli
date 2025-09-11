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

test_image_checksum "nginx:1.23.2" "8f3b10ad53968ece9ce635beecfe4259b919adc0"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "71f537de576b9d9d703e9d8a2e1d881859a42f30"
test_image_checksum "mysql:8.0.31" "3467be663daf828b03ffc7fad2b54e7ec1909603" stig
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "0b91145e2803d583660a0c9fe35b38eb4b237ba9"
test_image_checksum "postgres:15.1" "2a57a740527dc764ae5f1c5ec1ca33569af04f42" soc2
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "cb58c236cad99d58cdd101e35e58b1c630e61d3f"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "2e5b980ae82cba3ab798fb1ac19e60f0db73a7f0"
test_image_checksum "mariadb:10.9.4" "22ce36152412aaf1d16daf325ca276251e6f4cff" hipaa
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "15a723fd1a7e6786be15102f1b5b1ed947fad4b0"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "42100c7b7095c6ef33ee0a9cd673807ab8d3daa6"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "7dc3f7114703006cf8de53cfda6058c98438e930"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "23bd82b42026bbd427c3e76747e70bd41be70be5"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "a43130c2317fd24eb8a668fbd382e358c317eb99"
docker image rm "redis:7.0.5"
test_image_checksum "rethinkdb:2.4.4-bookworm-slim" "5c24a46b58d6ce1dbd02860548631b6e4a459d2d"
docker image rm "rethinkdb:2.4.4-bookworm-slim"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "ab91e44f19d522be75e98c52cfc6f727b06c4c7a"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Docker container tests
docker run --rm -d -e POSTGRES_PASSWORD=foo --name=demo-postgres postgres:15.1
test_container_checksum demo-postgres "a26bedf37bdddb18b952020d3983a1f9f1cf7445"
docker stop demo-postgres

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 20d681fa865190cab59fad652952e21cf24bcd9a
test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df e0e3b880a91fc182849577c9b9912b536dec8782 "" trivy_cve_scan
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 f6cdbb9311430a4f356255ae2a44298ef077054a
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 791ab1b8b5c522e7a4ebbda5c28a3751caa8426d
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 8d6f5d059215b339dd19218aa073048039ac5f52
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 4dbf1a5ebeeb397660d1bd57a2b694a938561d69
test_folder_checksum https://github.com/yiisoft/yii2.git 778d708c4f028c6997ff42ee2e1aead86cce3a64 f79b02fcc1f5e992a4fbe1a0e0daaf799ae67588 "" phpstan_sast_scan
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

# Test with a weird name
git clone https://github.com/ethereum/remix-project.git "$TEMP_DIR"/"tmp_repo_dir (1)";
(cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/"tmp_repo_dir (1)") | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}'

rm -rf "$TEMP_DIR"
