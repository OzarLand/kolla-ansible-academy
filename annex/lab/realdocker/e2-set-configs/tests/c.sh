# Test (c): a restart with a missing required source under restart policy unless-stopped
# (docker_restart_policy, group_vars/all.yml:134). Does the container restart-loop, and does it recover by itself?
t=c; c=e2-c-nova_compute; d=$(cfgdir $t); o=$OUT/c-restart-loop.txt
setup_nova_cfg $t base
run_nova $t
wait_starts $c 1
insp() { docker inspect -f 'RestartCount={{.RestartCount}} Status={{.State.Status}} Restarting={{.State.Restarting}} ExitCode={{.State.ExitCode}} Policy={{.HostConfig.RestartPolicy.Name}}' $c; }
{
  echo "# Test (c): missing required source + restart, restart policy unless-stopped, container $c"
  echo "before: $(insp) | docker ps: $(docker ps -a --filter name=^/$c\$ --format '{{.Status}}')"
} > "$o"

mv "$d/nova.conf" "$WORK/c-nova.conf.saved"
t0=$(date +%s); t0iso=$(date -u +%FT%T.%NZ)
docker stop -t 10 $c >/dev/null; docker start $c >/dev/null; echo "docker start rc=$? (nova.conf removed from the host dir)" >> "$o"
for s in 0 5 10 15 20 25 30 35 40 45 50 55 60; do
  while [ $(( $(date +%s) - t0 )) -lt $s ]; do sleep 0.2; done
  printf 't=%2ss %s | docker ps: %s\n' "$s" "$(insp)" "$(docker ps -a --filter name=^/$c\$ --format '{{.Status}}')" >> "$o"
  if [ $s = 20 ]; then
    echo "  docker exec -u root $c kolla_set_configs --check during the loop: rc $(check $c root "$WORK/c.chk"); $(head -c 200 "$WORK/c.chk")" >> "$o"
  fi
done
t1iso=$(date -u +%FT%T.%NZ)
echo "--- docker events start/die in the first 60 s:" >> "$o"
docker events --since "$t0iso" --until "$t1iso" --filter container=$c --filter event=start --filter event=die \
  --format '{{.TimeNano}} {{.Action}} exitCode={{index .Actor.Attributes "exitCode"}}' \
  | awk -v t0="$(date -d "$t0iso" +%s%N)" '{printf "  +%6.2fs %s %s\n", ($1-t0)/1e9, $2, $3}' >> "$o"
echo "--- error lines in docker logs (count of MissingRequiredSource: $(docker logs $c 2>&1 | grep -c MissingRequiredSource)):" >> "$o"
docker logs $c 2>&1 | grep -E 'MissingRequiredSource' | tail -n 2 | sed 's/^/  /' >> "$o"

# Restore the source and wait for the policy's next attempt (Docker's back-off grows to at most 1 min).
mv "$WORK/c-nova.conf.saved" "$d/nova.conf"; t2=$(date +%s)
n=$(starts $c)
back=no
for i in $(seq 1 240); do
  if [ "$(docker inspect -f '{{.State.Status}}' $c)" = running ] && [ "$(starts $c)" -gt "$n" ]; then back=yes; break; fi
  sleep 0.5
done
echo "after restoring nova.conf at t=$((t2 - t0))s: service started again without operator action: $back, after $(( $(date +%s) - t2 ))s: $(insp) | docker ps: $(docker ps -a --filter name=^/$c\$ --format '{{.Status}}')" >> "$o"
docker rm -f $c >/dev/null
log "test c done"
