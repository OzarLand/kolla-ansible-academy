#!/bin/bash
# stand-in service: logs every signal it receives, like a daemon would see them
log=/var/log/kolla/svc.log
trap 'echo "$(date +%s.%N) svc[$$] got TERM" >> $log; exit 0' TERM
trap 'echo "$(date +%s.%N) svc[$$] got HUP" >> $log' HUP
echo "$(date +%s.%N) svc[$$] start" >> $log
while true; do sleep 0.2; done
