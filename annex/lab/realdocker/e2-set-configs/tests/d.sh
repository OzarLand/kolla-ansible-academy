# Test (d): xtrace of kolla_start in a KOLLA_BOOTSTRAP one-shot. The image runs the real heat-base extend_start.sh
# (kolla_extend_start) which sources the real heat-api extend_start.sh (kolla_heat_extend_start); its line 12 runs
# "openstack user create ... --password ${HEAT_DOMAIN_ADMIN_PASSWORD}". The container is started like
# roles/heat/tasks/bootstrap_service.yml:2-29 (detach False, restart_policy no, label BOOTSTRAP, KOLLA_BOOTSTRAP empty).
t=d; c=e2-d-bootstrap_heat; d=$WORK/$t/heat-api; o=$OUT/d-xtrace-password.txt
mkdir -p "$d"
cp "$VAR/heat-api/config.json" "$d/config.json"
printf '[DEFAULT]\n# e2 stand-in heat.conf\n' > "$d/heat.conf"
printf '# e2 stand-in wsgi-heat-api.conf\n' > "$d/wsgi-heat-api.conf"
fix_layout "$d"
docker volume create --label $E2_LABEL e2-d-kolla_logs >/dev/null
# heat_api_default_volumes (roles/heat/defaults/main.yml:85-90), without the dev-mode mount
docker run -d --name $c --label $E2_LABEL --label BOOTSTRAP= --network host --restart no \
  -e KOLLA_BOOTSTRAP= -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS \
  -e OS_AUTH_URL=http://127.0.0.1:18235/v3 -e OS_IDENTITY_API_VERSION=3 -e OS_INTERFACE=internal \
  -e OS_USERNAME=admin -e OS_PASSWORD=e2-admin-pw -e OS_PROJECT_NAME=admin -e OS_REGION_NAME=RegionOne \
  -e HEAT_DOMAIN_ADMIN_PASSWORD=s3cr3t \
  -v "$d/:$CCD/:ro" -v /etc/localtime:/etc/localtime:ro -v /etc/timezone:/etc/timezone:ro \
  -v e2-d-kolla_logs:/var/log/kolla/ $IMG_HEAT >/dev/null
rc=$(docker wait $c)
docker logs $c > "$WORK/d.stdout" 2> "$WORK/d.stderr"
{
  echo "# Test (d): one-shot $c (image $IMG_HEAT), KOLLA_BOOTSTRAP='' HEAT_DOMAIN_ADMIN_PASSWORD=s3cr3t OS_PASSWORD=e2-admin-pw"
  echo "container exit code: $rc"
  echo "lines containing 's3cr3t' in docker logs stderr: $(grep -c s3cr3t "$WORK/d.stderr")"
  echo "lines containing 's3cr3t' in docker logs stdout: $(grep -c s3cr3t "$WORK/d.stdout")"
  echo "lines containing 'e2-admin-pw' (OS_PASSWORD, environment only) in stdout+stderr: $(cat "$WORK/d.stdout" "$WORK/d.stderr" | grep -c e2-admin-pw)"
  echo "--- docker logs stderr from the one-shot branch on (xtrace):"
  sed -n '/kolla_extend_start/,$p' "$WORK/d.stderr" | sed 's/^/  /'
  echo "--- docker logs stdout (stand-ins print no arguments beyond the first two words):"
  sed 's/^/  /' "$WORK/d.stdout"
  echo "--- the same value is also in the container's configuration (docker inspect Config.Env):"
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $c | grep HEAT_DOMAIN | sed 's/^/  /'
} > "$o"
docker rm -f $c >/dev/null
log "test d done"
