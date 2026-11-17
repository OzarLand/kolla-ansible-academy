# Test (g): memcached shape - config.json with empty config_files, all settings in the command
# (roles/memcached/templates/memcached.json.j2). The memcached binary is the real one (bionic package).
t=g; c=e2-g-memcached; d=$WORK/$t/memcached; o=$OUT/g-memcached-command.txt
mkdir -p "$d"; cp "$VAR/memcached/v1.json" "$d/config.json"; fix_layout "$d"
# memcached_default_volumes (roles/memcached/defaults/main.yml:37-40); kolla_docker: network_mode host
docker run -d --name $c --label $E2_LABEL --network host --restart unless-stopped \
  -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS \
  -v "$d/:$CCD/:ro" -v /etc/localtime:/etc/localtime:ro -v /etc/timezone:/etc/timezone:ro $IMG_MC >/dev/null
# stats <port>: ask memcached on 127.0.0.1:<port> (host network) for pid and limit_maxbytes
stats() {
  docker exec $c python3 -c "
import socket,sys
try:
    s=socket.create_connection(('127.0.0.1',$1),timeout=2); s.sendall(b'stats\r\n'); b=b''
    while not b.endswith(b'END\r\n'): b+=s.recv(4096)
    print(' '.join(l[5:] for l in b.decode().split('\r\n') if l.split(' ')[1:2] and l.split(' ')[1] in ('pid','limit_maxbytes')))
except Exception as e: print('port $1: %s' % e)"
}
waitport() { local i; for i in $(seq 1 40); do stats "$1" | grep -q limit_maxbytes && return 0; sleep 0.25; done; return 1; }
state() {
  {
    echo "## $1"
    echo "  /run_command: $(docker exec $c cat /run_command)"
    echo "  process: $(docker exec $c ps -o user=,args= -p "$(docker exec $c sh -c 'pgrep -P 1')")"
    echo "  port 18211: $(stats 18211) | port 18212: $(stats 18212)"
  } >> "$o"
}
echo "# Test (g): empty config_files + changed command, container $c (image $IMG_MC, USER memcached)" > "$o"
waitport 18211
state "g1 started with v1.json: $(grep command "$d/config.json" | sed 's/^ *//')"
cp "$VAR/memcached/v2.json" "$d/config.json"; fix_layout "$d"
{
  echo "## g2 host config.json changed to v2.json: $(grep command "$d/config.json" | sed 's/^ *//')"
  echo "  --check as root: rc $(check $c root "$WORK/g.chk") ($(tail -n1 "$WORK/g.chk"))"
  echo "  --check as image user: rc $(check $c user "$WORK/g.chk") ($(grep -o 'PermissionError.*' "$WORK/g.chk"))"
} >> "$o"
state "g2 container still running the old command (no restart yet)"
kolla_restart $c
waitport 18212
state "g3 after a plain restart (docker stop -t 10 + docker start)"
docker rm -f $c >/dev/null
log "test g done"
