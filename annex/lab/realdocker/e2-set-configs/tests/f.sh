# Test (f): the recursive "permissions" of nova-compute.json.j2 (/var/lib/nova and /var/log/kolla/nova, recurse true)
# on every start under COPY_ALWAYS, and under COPY_ONCE on a second start of the same container.
o=$OUT/f-permissions-recurse.txt
NFILES=${E2_NFILES:-5000}
echo "# Test (f): permissions with recurse; probe file chowned to root inside the container, then a restart" > "$o"

# per_start <container> <since>: "Setting permission for" log lines of one start, by tree.
per_start() {
  docker logs --since "$2" "$1" 2>&1 | grep 'Setting permission for' > "$WORK/f.perm"
  echo "Setting-permission lines: /var/lib/nova $(grep -c 'for /var/lib/nova' "$WORK/f.perm"), /var/log/kolla/nova $(grep -c 'for /var/log/kolla/nova' "$WORK/f.perm"), total $(wc -l < "$WORK/f.perm")"
}
entries() { docker exec -u root "$1" sh -c 'echo "entries under /var/lib/nova (incl. itself): $(find /var/lib/nova | wc -l), under /var/log/kolla/nova: $(find /var/log/kolla/nova | wc -l)"'; }
probe() { docker exec -u root "$1" stat -c '%U:%G %a %n' /var/lib/nova/instances/e2-probe /var/lib/nova/instances/e2-many/f1 /var/log/kolla/nova/e2-probe.log; }
spoil() {  # create the probe files and chown them to root (as an operator or a root process inside the container would)
  docker exec -u root "$1" sh -c "mkdir -p /var/lib/nova/instances/e2-many && cd /var/lib/nova/instances/e2-many \
    && seq 1 $NFILES | sed 's/^/f/' | xargs touch && touch /var/lib/nova/instances/e2-probe /var/log/kolla/nova/e2-probe.log \
    && chown -R root:root /var/lib/nova/instances/e2-probe /var/lib/nova/instances/e2-many /var/log/kolla/nova/e2-probe.log"
}
# set_configs_span <container> <since>: wall time from the first to the last "Setting permission" line of one start
set_configs_span() {
  docker logs --timestamps --since "$2" "$1" 2>&1 | grep 'Setting permission for /var/lib/nova' \
    | sed -n '1p;$p' | awk '{print $1}' > "$WORK/f.ts"
  if [ "$(wc -l < "$WORK/f.ts")" = 2 ]; then
    echo "$(( ($(date -d "$(sed -n 2p "$WORK/f.ts")" +%s%N) - $(date -d "$(sed -n 1p "$WORK/f.ts")" +%s%N)) / 1000000 )) ms"
  else echo "n/a (no walk)"; fi
}

for STRATEGY in COPY_ALWAYS COPY_ONCE; do
  t=f-$(echo ${STRATEGY#COPY_} | tr 'A-Z' 'a-z'); c=e2-$t-nova_compute
  setup_nova_cfg $t base
  s1=$(date -u +%FT%T.%NZ); run_nova $t; wait_starts $c 1
  {
    echo "## $STRATEGY, container $c"
    echo "  start 1: $(per_start $c "$s1")"
  } >> "$o"
  spoil $c
  { echo "  $(entries $c)"; echo "  before restart:"; probe $c | sed 's/^/    /'; } >> "$o"
  [ $STRATEGY = COPY_ONCE ] && set_variant $t cmd   # also change the command before the second start
  s2=$(date -u +%FT%T.%NZ); kolla_restart $c; wait_starts $c 2
  {
    echo "  start 2 (restart): $(per_start $c "$s2"); span of the /var/lib/nova walk in the log: $(set_configs_span $c "$s2")"
    echo "  after restart:"; probe $c | sed 's/^/    /'
    echo "  set_configs result lines of start 2: $(docker logs --since "$s2" $c 2>&1 | grep -E 'ImmutableConfig|config strategy' | tr '\n' ' ')"
    echo "  /run_command after start 2: $(docker exec $c cat /run_command); /configured: $(docker exec $c sh -c 'ls -l /configured 2>&1')"
    echo "  --check as root after start 2: rc $(check $c root "$WORK/f.chk") $(decisive "$WORK/f.chk")"
  } >> "$o"
  if [ $STRATEGY = COPY_ALWAYS ]; then
    s3=$(date -u +%FT%T.%NZ); kolla_restart $c; wait_starts $c 3
    echo "  start 3 (restart, nothing changed): $(per_start $c "$s3"); span: $(set_configs_span $c "$s3")" >> "$o"
  fi
  docker rm -f $c >/dev/null
done
unset STRATEGY
log "test f done"
