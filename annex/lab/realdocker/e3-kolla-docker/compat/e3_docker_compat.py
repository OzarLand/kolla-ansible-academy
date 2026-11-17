# e3 compat shim, loaded at interpreter start in the e3 venv only (e3_docker_compat.pth, written by setup-venv.sh).
# Docker 29 no longer returns HostConfig.KernelMemory at any API version it accepts (1.40-1.56); Docker 19.03/20.10,
# the daemons of the Ussuri era, returned "KernelMemory": 0. kolla_docker.py:500-516 (compare_dimensions) reads
# current_dimensions['KernelMemory'] unconditionally and raises KeyError, so every comparison of an EXISTING
# container fails. This shim restores the old response shape (KernelMemory 0 when absent) and changes nothing else.
# The kolla_docker module file itself is used unmodified. Set E3_NO_SHIM=1 to disable it.
import os

if not os.environ.get('E3_NO_SHIM'):
    try:
        import docker.api.container as _c

        _orig = _c.ContainerApiMixin.inspect_container

        def inspect_container(self, container):
            info = _orig(self, container)
            hc = info.get('HostConfig') if isinstance(info, dict) else None
            if isinstance(hc, dict) and 'KernelMemory' not in hc:
                hc['KernelMemory'] = 0
            return info

        inspect_container.__doc__ = _orig.__doc__
        _c.ContainerApiMixin.inspect_container = inspect_container
    except ImportError:
        pass
