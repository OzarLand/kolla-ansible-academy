#!/bin/bash
# Build the lab copy of kolla-ansible ussuri-eol with stub modules.
set -e
S=${KOLLA_LAB_ROOT:-$HOME/kolla-lab}
HERE=$(cd "$(dirname "$0")" && pwd)
LAB=$S/lab
rm -rf $LAB/kolla-ansible && mkdir -p $LAB/kolla-ansible
cp -r $S/src/kolla-ansible/ansible $LAB/kolla-ansible/ansible
mkdir -p $LAB/callback && cp $HERE/lab_trace.py $LAB/callback/
for f in $HERE/stub_*.py; do
  mod=$(basename $f .py); mod=${mod#stub_}
  python3 - "$f" "$HERE/stubcommon.py" "$LAB/kolla-ansible/ansible/library/$mod.py" <<'PY'
import sys
src=open(sys.argv[1]).read(); common=open(sys.argv[2]).read()
open(sys.argv[3],'w').write(src.replace('#@@COMMON@@', common))
PY
done
echo "lab built: $(ls $LAB/kolla-ansible/ansible/library | tr '\n' ' ')"
