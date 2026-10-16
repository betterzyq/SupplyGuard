#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_USER=supplyguard-svc
RUNTIME=/opt/supplyguard-runtime
DATA_DIR=/var/lib/supplyguard
LOG_DIR=/var/log/supplyguard
RUN_DIR=/run/supplyguard
PGDATA=$DATA_DIR/postgres
NEO4J_HOME=$RUNTIME/neo4j
NEO4J_CONF=/etc/supplyguard/neo4j

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Run this command as root." >&2
        exit 1
    fi
}

ensure_dirs() {
    install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 \
        "$DATA_DIR" "$DATA_DIR/postgres" "$DATA_DIR/redis" \
        "$DATA_DIR/qdrant" "$DATA_DIR/neo4j" "$DATA_DIR/minio" \
        "$LOG_DIR" "$LOG_DIR/postgres" "$LOG_DIR/redis" \
        "$LOG_DIR/qdrant" "$LOG_DIR/neo4j" "$LOG_DIR/minio" \
        "$RUN_DIR" "$RUN_DIR/neo4j"
}

run_service() {
    runuser -u "$SERVICE_USER" -- "$@"
}

port_in_use() {
    netstat -lnt 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$1$"
}

assert_port_free() {
    local name=$1 port=$2
    if port_in_use "$port"; then
        echo "Cannot start $name: localhost port $port is already in use." >&2
        return 1
    fi
}

wait_for_port() {
    local name=$1 port=$2 unused
    for unused in $(seq 1 120); do
        if port_in_use "$port"; then
            return
        fi
        sleep 0.5
    done
    echo "$name did not become ready on port $port." >&2
    return 1
}

pid_is_running() {
    local pidfile=$1 pid owner state command expected birth
    [ -s "$pidfile" ] || return 1
    pid=$(cat "$pidfile")
    [[ "$pid" =~ ^[0-9]+$ ]] && [ "$pid" -gt 1 ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    owner=$(stat -c %U "/proc/$pid" 2>/dev/null || true)
    [ "$owner" = "$SERVICE_USER" ] || return 1
    state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || true)
    [ "$state" != Z ] || return 1
    command=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
    case "$(basename "$pidfile")" in
        qdrant.pid) expected="$RUNTIME/bin/qdrant" ;;
        neo4j.pid) expected="-Dapp.home=$NEO4J_HOME" ;;
        redis.pid) expected="$RUNTIME/bin/redis-server 127.0.0.1:6379" ;;
        minio.pid) expected="$RUNTIME/bin/minio server $DATA_DIR/minio" ;;
        s3.pid) expected="$RUNTIME/bin/moto_server" ;;
        *) return 1 ;;
    esac
    [[ "$command" == *"$expected"* ]] || return 1
    if [ -s "$pidfile.birth" ]; then
        birth=$(awk '{print $22}' "/proc/$pid/stat")
        [ "$birth" = "$(cat "$pidfile.birth")" ] || return 1
    fi
}

record_identity() {
    local pidfile=$1 pid
    pid_is_running "$pidfile" || return 1
    pid=$(cat "$pidfile")
    awk '{print $22}' "/proc/$pid/stat" > "$pidfile.birth"
    chmod 0600 "$pidfile.birth"
}

prepare_pidfile() {
    local pidfile=$1
    if [ -s "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null &&
        [ "$(awk '{print $3}' "/proc/$(cat "$pidfile")/stat" 2>/dev/null)" != Z ]; then
        echo "Refusing to replace an unrecognized live PID in $pidfile." >&2
        return 1
    fi
    rm -f "$pidfile" "$pidfile.birth"
}

start_postgres() {
    if run_service "$RUNTIME/bin/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
        echo "postgres: already running"
        return
    fi
    assert_port_free postgres 5432
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
        run_service "$RUNTIME/bin/initdb" -D "$PGDATA" \
            --username=supplyguard --encoding=UTF8 --locale=C.UTF-8 \
            --auth-local=trust --auth-host=scram-sha-256
    fi
    run_service "$RUNTIME/bin/pg_ctl" -D "$PGDATA" \
        -l "$LOG_DIR/postgres/postgres.log" \
        -o "-h 127.0.0.1 -p 5432 -k $RUN_DIR" start -w
    run_service "$RUNTIME/bin/psql" -h "$RUN_DIR" -p 5432 \
        -U supplyguard -d postgres -v ON_ERROR_STOP=1 \
        -c "ALTER ROLE supplyguard WITH PASSWORD 'supplyguard';" >/dev/null
    if ! run_service "$RUNTIME/bin/psql" -h "$RUN_DIR" -p 5432 \
        -U supplyguard -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='supplyguard'" | grep -q 1; then
        run_service "$RUNTIME/bin/createdb" -h "$RUN_DIR" -p 5432 \
            -U supplyguard supplyguard
    fi
    echo "postgres: started on 127.0.0.1:5432"
}

start_redis() {
    if pid_is_running "$RUN_DIR/redis.pid"; then
        echo "redis: already running"
        return
    fi
    assert_port_free redis 6379
    prepare_pidfile "$RUN_DIR/redis.pid"
    run_service "$RUNTIME/bin/redis-server" /etc/supplyguard/redis.conf
    wait_for_port redis 6379
    record_identity "$RUN_DIR/redis.pid"
    echo "redis: started on 127.0.0.1:6379"
}

start_qdrant() {
    if pid_is_running "$RUN_DIR/qdrant.pid"; then
        echo "qdrant: already running"
        return
    fi
    assert_port_free qdrant 6333
    assert_port_free qdrant-grpc 6334
    prepare_pidfile "$RUN_DIR/qdrant.pid"
    start-stop-daemon --start --background --make-pidfile \
        --pidfile "$RUN_DIR/qdrant.pid" --chuid "$SERVICE_USER" \
        --output "$LOG_DIR/qdrant/qdrant.log" --nicelevel 5 \
        --chdir "$DATA_DIR/qdrant" --startas /usr/bin/env -- \
        QDRANT__STORAGE__STORAGE_PATH="$DATA_DIR/qdrant/storage" \
        QDRANT__SERVICE__HOST=127.0.0.1 \
        QDRANT__SERVICE__HTTP_PORT=6333 \
        QDRANT__SERVICE__GRPC_PORT=6334 \
        QDRANT__TELEMETRY_DISABLED=true \
        QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=2 \
        "$RUNTIME/bin/qdrant"
    wait_for_port qdrant 6333
    record_identity "$RUN_DIR/qdrant.pid"
    echo "qdrant: started on 127.0.0.1:6333/6334"
}

start_neo4j() {
    if pid_is_running "$RUN_DIR/neo4j.pid"; then
        echo "neo4j: already running"
        return
    fi
    assert_port_free neo4j-http 7474
    assert_port_free neo4j-bolt 7687
    prepare_pidfile "$RUN_DIR/neo4j.pid"
    if [ ! -f "$DATA_DIR/neo4j/.password-initialized" ]; then
        run_service env JAVA_HOME="$RUNTIME" NEO4J_CONF="$NEO4J_CONF" \
            "$NEO4J_HOME/bin/neo4j-admin" dbms set-initial-password supplyguard
        run_service touch "$DATA_DIR/neo4j/.password-initialized"
    fi
    rm -f "$RUN_DIR/neo4j/neo4j.pid"
    start-stop-daemon --start --background --make-pidfile \
        --pidfile "$RUN_DIR/neo4j.pid" --chuid "$SERVICE_USER" \
        --output "$LOG_DIR/neo4j/console.log" --nicelevel 5 \
        --chdir "$NEO4J_HOME" --startas /usr/bin/env -- \
        JAVA_HOME="$RUNTIME" NEO4J_CONF="$NEO4J_CONF" \
        JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2 \
        "$NEO4J_HOME/bin/neo4j" console
    wait_for_port neo4j 7687
    record_identity "$RUN_DIR/neo4j.pid"
    echo "neo4j: started on 127.0.0.1:7474/7687"
}

start_minio() {
    if pid_is_running "$RUN_DIR/minio.pid"; then
        echo "minio: already running"
        return
    fi
    assert_port_free minio 9000
    assert_port_free minio-console 9001
    prepare_pidfile "$RUN_DIR/minio.pid"
    start-stop-daemon --start --background --make-pidfile \
        --pidfile "$RUN_DIR/minio.pid" --chuid "$SERVICE_USER" \
        --output "$LOG_DIR/minio/minio.log" --nicelevel 5 \
        --chdir "$DATA_DIR/minio" --startas /usr/bin/env -- \
        MINIO_ROOT_USER=supplyguard MINIO_ROOT_PASSWORD=supplyguard123 \
        GOMAXPROCS=2 "$RUNTIME/bin/minio" server "$DATA_DIR/minio" \
        --address 127.0.0.1:9000 --console-address 127.0.0.1:9001
    wait_for_port minio 9000
    record_identity "$RUN_DIR/minio.pid"
    echo "minio: started on 127.0.0.1:9000/9001"
}

stop_pid_service() {
    local name=$1 pidfile=$2 pid group unused
    if ! pid_is_running "$pidfile"; then
        prepare_pidfile "$pidfile"
        echo "$name: not running"
        return
    fi
    pid=$(cat "$pidfile")
    # Daemonized processes have a private process group; Neo4j also has a child JVM.
    group=$(ps -p "$pid" -o pgid= | tr -d ' ')
    if [ "$group" = "$(ps -p $$ -o pgid= | tr -d ' ')" ] ||
        ps -eo pgid=,uid= | awk -v g="$group" -v u="$(id -u "$SERVICE_USER")" \
            '$1==g && $2!=u {bad=1} END {exit !bad}'; then
        echo "Refusing to stop $name: process group is not exclusive." >&2
        return 1
    fi
    kill -TERM -- "-$group"
    for unused in $(seq 1 120); do
        if ! ps -eo pgid=,stat= | awk -v g="$group" \
            '$1==g && $2 !~ /^Z/ {alive=1} END {exit !alive}'; then
            break
        fi
        sleep 0.25
    done
    if ps -eo pgid=,stat= | awk -v g="$group" \
        '$1==g && $2 !~ /^Z/ {alive=1} END {exit !alive}'; then
        echo "$name has not stopped; preserving its PID file for diagnosis." >&2
        return 1
    fi
    rm -f "$pidfile" "$pidfile.birth"
    echo "$name: stopped"
}

stop_all() {
    stop_pid_service minio "$RUN_DIR/minio.pid"
    stop_pid_service neo4j "$RUN_DIR/neo4j.pid"
    stop_pid_service qdrant "$RUN_DIR/qdrant.pid"
    if pid_is_running "$RUN_DIR/redis.pid"; then
        "$RUNTIME/bin/redis-cli" -h 127.0.0.1 -p 6379 shutdown >/dev/null
        echo "redis: stopped"
    else
        echo "redis: not running"
    fi
    if run_service "$RUNTIME/bin/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
        run_service "$RUNTIME/bin/pg_ctl" -D "$PGDATA" stop -m fast -w
        echo "postgres: stopped"
    else
        echo "postgres: not running"
    fi
}

status_all() {
    if run_service "$RUNTIME/bin/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then echo "postgres: running"; else echo "postgres: stopped"; fi
    if "$RUNTIME/bin/redis-cli" -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG; then echo "redis: running"; else echo "redis: stopped"; fi
    if pid_is_running "$RUN_DIR/qdrant.pid"; then echo "qdrant: running"; else echo "qdrant: stopped"; fi
    if pid_is_running "$RUN_DIR/neo4j.pid" && port_in_use 7687; then echo "neo4j: running"; else echo "neo4j: stopped"; fi
    if pid_is_running "$RUN_DIR/minio.pid" && port_in_use 9000; then echo "minio: running"; else echo "minio: stopped"; fi
}

start_all() {
    ensure_dirs
    start_postgres
    start_redis
    start_qdrant
    start_neo4j
    start_minio
    status_all
}

require_root
action=help
if [ "$#" -gt 0 ]; then action=$1; fi
case "$action" in
    up|start) start_all ;;
    down|stop) ensure_dirs; stop_all ;;
    restart) ensure_dirs; stop_all; start_all ;;
    status) ensure_dirs; status_all ;;
    *) echo "Usage: $0 {up|down|restart|status}"; exit 2 ;;
esac
