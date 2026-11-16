# ---- lab stub common helpers (inlined into every stub module) ----
import json, os, time, hashlib, fcntl, re
LAB_RUN = os.environ.get('LAB_RUN') or '__LAB_RUN__'
HOST = os.environ.get('LAB_HOST', 'localhost')

def _locked_rw(path, fn):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        raw = f.read()
        data = json.loads(raw) if raw.strip() else {}
        out = fn(data)
        f.seek(0); f.truncate(); f.write(json.dumps(data, indent=1, sort_keys=True))
        fcntl.flock(f, fcntl.LOCK_UN)
        return out

def state(fn, host=None):
    return _locked_rw(os.path.join(LAB_RUN, 'state', (host or HOST) + '.json'), fn)

def registry():
    p = os.path.join(LAB_RUN, 'registry.json')
    try:
        return json.load(open(p))
    except Exception:
        return {}

def image_digest(image):
    # Registry digest for an image reference; default derives from the name
    # so that a tag change (e.g. openstack_tag) yields a new digest.
    reg = registry()
    if image in reg:
        return reg[image]
    return 'sha256:' + hashlib.sha256(image.encode()).hexdigest()[:16]

def log_event(module, **kw):
    ev = dict(ts=round(time.time(), 3), host=HOST, module=module)
    ev.update(kw)
    p = os.path.join(LAB_RUN, 'events.jsonl')
    os.makedirs(LAB_RUN, exist_ok=True)
    with open(p, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(ev, sort_keys=True) + '\n')
        fcntl.flock(f, fcntl.LOCK_UN)

def dir_hash(path):
    if not path or not os.path.isdir(path):
        return None
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            h.update(fp[len(path):].encode())
            try:
                h.update(open(fp, 'rb').read())
            except Exception:
                pass
    return h.hexdigest()[:16]
