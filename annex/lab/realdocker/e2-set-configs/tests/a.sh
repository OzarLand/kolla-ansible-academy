# Test (a): kolla_set_configs --check exit codes in a running nova_compute-shaped container (USER nova),
# as the image user (plain docker exec) and as root (docker exec -u root, what kolla_docker does).
t=a; c=e2-a-nova_compute; d=$(cfgdir $t); o=$OUT/a-check-exit-codes.txt; raw=$OUT/a-check-raw.txt
: > "$raw"
setup_nova_cfg $t base
run_nova $t
wait_starts $c 1
n_start=1

# restart_with <variant>: apply a config with a kolla-style restart and wait for the service.
restart_with() { set_variant $t "$1"; kolla_restart $c; n_start=$((n_start + 1)); wait_starts $c $n_start; }
# row <case> <expected per annex §3.3> : run --check as user and as root, record.
row() {
  local u r
  u=$(check $c user "$WORK/a.user"); r=$(check $c root "$WORK/a.root")
  printf '%-60s %-8s %-6s %-6s %s\n' "$1" "$2" "$u" "$r" "$(decisive "$WORK/a.root")" >> "$o"
  { echo "### $1 (user rc=$u, root rc=$r)"; echo "  as image user: $(tail -n 1 "$WORK/a.user")"
    grep -v -e 'Loading config file' -e 'Validating config file' "$WORK/a.root" | sed 's/^/  as root: /'; } >> "$raw"
}
nova_rev() { printf '[DEFAULT]\n# e2 stand-in nova.conf, revision %s\n' "$1" > "$d/nova.conf"; fix_layout "$d"; }

{
  echo "# Test (a): kolla_set_configs --check exit codes, container $c (image $IMG_NOVA, USER nova)"
  echo "# user = docker exec $c /usr/local/bin/kolla_set_configs --check ; root = same with -u root"
  echo "# expected = annex/kolla-images.md §3.3 table and scratch-run line (exit code as root)"
  printf '%-60s %-8s %-6s %-6s %s\n' "case" "expected" "user" "root" "decisive line of the root run"
} > "$o"

row "a01 no change" 0
s=$(check $c sudo "$WORK/a.sudo"); echo "a01b no change, 'docker exec $c sudo kolla_set_configs --check' -> rc $s" >> "$o"

nova_rev 2;                          row "a02 changed content (nova.conf on host)" 1
nova_rev 1
set_variant $t perm;                 row "a03 config.json perm of nova.conf 0600->0640" 1
set_variant $t owner;                row "a04 config.json owner of nova.conf nova->root:nova" 1
set_variant $t base
docker exec -u root $c chmod 0644 /etc/nova/nova.conf
row "a05 dest mode changed in container (chmod 0644)" 1
docker exec -u root $c sh -c 'chmod 0600 /etc/nova/nova.conf; chown root:nova /etc/nova/nova.conf'
row "a05b dest owner changed in container (chown root)" 1
docker exec -u root $c sh -c 'chmod 0600 /etc/nova/nova.conf; chown nova:nova /etc/nova/nova.conf'
row "a05c container file restored by hand" 0
set_variant $t cmd;                  row "a06 config.json command-only change" 0
set_variant $t permsonly;            row "a07 config.json permissions-only change" 0
set_variant $t nosasl;               row "a08 dropped entry (auth.conf, libvirt_enable_sasl off)" 0
set_variant $t nopolicy;             row "a08b dropped entry (custom policy file)" 0
set_variant $t base
printf 'e2-release-1\n' > "$d/release"; fix_layout "$d"
row "a09 new optional file (release), alone" 2
nova_rev 2
row "a10 new optional file + earlier entry changed (nova.conf)" 1
nova_rev 1
printf '[credentials-default]\nusername = nova\npassword = e2-changed\n' > "$d/auth.conf"; fix_layout "$d"
row "a10b new optional file + later entry changed (auth.conf)" 2
printf '[credentials-default]\nusername = nova\npassword = e2-not-a-secret\n' > "$d/auth.conf"; fix_layout "$d"
restart_with base                                       # release now copied into the container
row "a11 optional file present on both sides (after restart)" 0
rm -f "$d/release";                  row "a11b optional source removed from host" 0

# preserve_properties entry (prometheus extras shape): applied by a restart, then checked twice without any change
mkdir -p "$d/extras"; printf 'e2: extra\n' > "$d/extras/e2-extra.yml"; fix_layout "$d"
restart_with preserve
row "a12 preserve_properties entry, right after restart" 1
row "a12b preserve_properties entry, second check" 1
rm -rf "$d/extras"

# directory source with a subdirectory (haproxy services.d shape), and a flat directory as control
mkdir -p "$d/e2.d"; printf 'a\n' > "$d/e2.d/one.cfg"; fix_layout "$d"
restart_with dir
row "a13 flat directory source (control), after restart" 0
mkdir -p "$d/e2.d/sub"; printf 'b\n' > "$d/e2.d/sub/two.cfg"; fix_layout "$d"
restart_with dir
row "a13b directory source with a subdirectory, after restart" 1
row "a13c directory source with a subdirectory, second check" 1
docker exec -u root $c stat -c '%a %U:%G %n' /etc/nova /etc/nova/e2.d /etc/nova/e2.d/sub /etc/nova/e2.d/sub/two.cfg \
  > "$WORK/a.dirstat"
sed 's/^/    dir modes in container: /' "$WORK/a.dirstat" >> "$o"
rm -rf "$d/e2.d"

restart_with base
row "a14 baseline again" 0
mv "$d/nova.conf" "$WORK/nova.conf.saved"; row "a14b missing required source (nova.conf)" 1
mv "$WORK/nova.conf.saved" "$d/nova.conf"
set_variant $t invalid;              row "a15 invalid JSON in config.json" 1
set_variant $t base;                 row "a16 baseline restored" 0

docker rm -f $c >/dev/null
log "test a done"
