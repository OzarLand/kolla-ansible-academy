# Test (b): what a kolla-style restart (docker stop -t 10 + docker start of the same container) applies, and what a
# recreate (docker rm + docker run with the same parameters and volumes) changes, for COPY_ALWAYS.
t=b; c=e2-b-nova_compute; d=$(cfgdir $t); o=$OUT/b-restart-applies.txt
files="/etc/nova/nova.conf /etc/nova/policy.yaml /etc/nova/release /var/lib/nova/.config/libvirt/auth.conf"
setup_nova_cfg $t base
printf 'e2-release-1\n' > "$d/release"; fix_layout "$d"
run_nova $t
wait_starts $c 1

state() {   # state <title>
  {
    echo "## $1"
    echo "/run_command: $(docker exec $c cat /run_command)"
    echo "service process: $(docker exec $c ps -o args= -p "$(docker exec $c sh -c 'pgrep -P 1')")"
    echo "nova.conf in container: $(docker exec -u root $c grep revision /etc/nova/nova.conf 2>&1)"
    for f in $files; do echo "  $(docker exec -u root $c stat -c '%U:%G %a %n' $f 2>&1 | sed 's/^stat: //')"; done
    echo "--check as root: rc $(check $c root "$WORK/b.chk") $(decisive "$WORK/b.chk")"
  } >> "$o"
}

echo "# Test (b): restart (kolla_docker restart_container = stop -t 10 + start) and recreate, container $c" > "$o"
echo "# config dir on host: $(ls "$d" | tr '\n' ' ')" >> "$o"
state "b0 initial start: base config.json (policy + auth.conf entries), release present"

# b1: changed file content and changed command, applied by a restart
printf '[DEFAULT]\n# e2 stand-in nova.conf, revision 2\n' > "$d/nova.conf"
set_variant $t cmd
echo "## b1 host: nova.conf revision 2 and config.json command changed; --check before restart: rc $(check $c root "$WORK/b.chk") $(decisive "$WORK/b.chk")" >> "$o"
kolla_restart $c; wait_starts $c 2
state "b1 after restart"

# b2: dropped entries (auth.conf on the nova_compute volume, policy.yaml in the writable layer), optional source removed
set_variant $t nosasl-nopolicy
rm -f "$d/release"
echo "## b2 host: config.json without the auth.conf and policy entries (files left on the host, as kolla-ansible does), release deleted on the host; host dir: $(ls "$d" | tr '\n' ' ')" >> "$o"
kolla_restart $c; wait_starts $c 3
state "b2 after restart"

# b3: recreate (kolla_docker stop + remove + start_container), same parameters and named volumes
docker stop -t 10 $c >/dev/null && docker rm $c >/dev/null
run_nova $t
wait_starts $c 1
state "b3 after recreate (docker rm + docker run, same volumes e2-b-*)"
docker logs $c 2>&1 | grep -E 'Copying|Deleting' | sed 's/^/  recreate start log: /' >> "$o"

docker rm -f $c >/dev/null
log "test b done"
