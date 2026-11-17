# Test (e): kolla_copy_cacerts on Ubuntu (kolla docker/base/copy_cacerts.sh), run by kolla_start through sudo as the
# image user on every start. Custom CAs come from <config dir>/ca-certificates/ (roles/service-cert-copy/tasks/main.yml).
t=e; c=e2-e-nova_compute; d=$(cfgdir $t); o=$OUT/e-cacerts.txt; ca=$WORK/cas
mkdir -p "$ca"
docker run --rm --network none -v "$ca:/cas" --entrypoint bash $IMG_RENDER -c '
  for n in 1 2; do
    openssl req -x509 -newkey rsa:2048 -nodes -keyout /dev/null -days 30 -subj "/CN=e2-lab-ca$n" -out /cas/ca$n.crt 2>/dev/null
  done' || exit 1
# A unique base64 line of each CA identifies it in the bundle.
mark() { sed -n '3p' "$ca/$1.crt"; }
inbundle() { docker exec $c grep -cxF "$(mark "$1")" /etc/ssl/certs/ca-certificates.crt; }
snap() {   # snap <title>
  {
    echo "## $1"
    echo "  host ca-certificates/: $([ -d "$d/ca-certificates" ] && echo "[$(ls "$d/ca-certificates" | tr "\n" " ")]" || echo "(no directory)")"
    echo "  /usr/local/share/ca-certificates: [$(docker exec $c ls /usr/local/share/ca-certificates | tr '\n' ' ')]"
    echo "  /etc/ssl/certs/kolla-customca-*: [$(docker exec $c sh -c 'ls /etc/ssl/certs | grep kolla-customca' | tr '\n' ' ')]; dangling symlinks in /etc/ssl/certs: [$(docker exec $c find /etc/ssl/certs -xtype l | tr '\n' ' ')]"
    echo "  ca1 in /etc/ssl/certs/ca-certificates.crt: $(inbundle ca1) | ca2: $(inbundle ca2) | bundle certs: $(docker exec $c grep -c 'BEGIN CERT' /etc/ssl/certs/ca-certificates.crt)"
    for x in ca1 ca2; do
      echo "  openssl verify $x: -CAfile bundle -> $(docker exec -i $c openssl verify -no-CApath -CAfile /etc/ssl/certs/ca-certificates.crt /dev/stdin < "$ca/$x.crt" 2>&1 | grep -oE 'OK|error [0-9]+' | head -n1); -CApath /etc/ssl/certs -> $(docker exec -i $c openssl verify -no-CAfile -CApath /etc/ssl/certs /dev/stdin < "$ca/$x.crt" 2>&1 | grep -oE 'OK|error [0-9]+' | head -n1)"
    done
    echo "  update-ca-certificates output of this start: $(docker logs --since "$since" $c 2>&1 | grep -E 'Updating certificates|added,|update-ca-certificates' | tr '\n' ' ')"
  } >> "$o"
}
restart() { since=$(date -u +%FT%T.%NZ); kolla_restart $c; n=$((n + 1)); wait_starts $c $n; }

echo "# Test (e): custom CA certificates across restarts, container $c (USER nova; ca-certificates $(docker run --rm --entrypoint dpkg-query $IMG_NOVA -W -f '${Version}' ca-certificates))" > "$o"
setup_nova_cfg $t base
mkdir -p "$d/ca-certificates"; cp "$ca/ca1.crt" "$d/ca-certificates/"; fix_layout "$d"
since=$(date -u +%FT%T.%NZ); run_nova $t; n=1; wait_starts $c 1
snap "e1 first start with ca1"
rm -f "$d/ca-certificates/ca1.crt"
restart; snap "e2 ca1 removed on the host (directory empty), restart"
docker rm -f $c >/dev/null
since=$(date -u +%FT%T.%NZ); run_nova $t; n=1; wait_starts $c 1
snap "e2b same, after a recreate (docker rm + docker run)"
cp "$ca/ca1.crt" "$ca/ca2.crt" "$d/ca-certificates/"; fix_layout "$d"
restart; snap "e3 ca1 and ca2 on the host, restart"
rm -f "$d/ca-certificates/ca2.crt"
restart; snap "e4 ca2 removed on the host (ca1 kept), restart"
rm -rf "$d/ca-certificates"
restart; snap "e5 whole ca-certificates directory removed on the host (ca1 was still in it), restart"
docker rm -f $c >/dev/null
log "test e done"
