"""External shared-pip read-only policy/independence probe; executed as isolated source."""
import hashlib
import json
import sys
import sysconfig
from importlib import metadata
from pathlib import Path


def main():
    bundle, prefix, shared = sys.argv[1:]
    sys.path.insert(0, bundle)
    import manager_network as policy
    import manager_tool_probe as probe
    target = Path(prefix)
    for value in (sys.executable, sys.prefix, sys.base_prefix, sysconfig.get_path('stdlib'), *sys.path): probe.outside(value, target)
    if Path(sys.prefix).resolve() != Path(shared).resolve() or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise probe.Refused('Shared pip runtime did not preserve its reviewed prefix')
    dist = metadata.distribution('pip')
    inventory = probe.inventory_files(dist, target)
    from pip._internal.configuration import Configuration
    config = Configuration(isolated=False)
    config.load()
    expected = {':env:.' + name[4:].lower().replace('_', '-'): value for name, value in policy.PIP.items()}
    values = dict(config.items())
    # Inspected pip 26.3 groups by filename; earlier pip returns flat key/value pairs. Refuse
    # unknown/mixed layouts rather than infer success from a missing key or human diagnostic.
    if values and all(isinstance(value, dict) for value in values.values()):
        rows = [(key, value) for group in values.values() for key, value in group.items()]
        if len(rows) != len(dict(rows)): raise probe.Refused('Ambiguous effective pip policy')
        values = dict(rows)
    if values != expected: raise probe.Refused('Effective pip policy differs from public defaults')
    origins = set()
    for module in tuple(sys.modules.values()):
        value = getattr(module, '__file__', None)
        if value: origins.add(probe.outside(value, target))
        for value in getattr(module, '__path__', ()): probe.outside(value, target)
    for value in sys.path: probe.outside(value, target)
    print(json.dumps({'ok': True, 'version': dist.version, 'prefix': str(Path(sys.prefix).resolve()),
                      'policy': 'public-defaults', 'inventory_sha256': hashlib.sha256(json.dumps(sorted(inventory)).encode()).hexdigest(),
                      'origins': sorted(origins)}))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, AttributeError, RecursionError):
        print(json.dumps({'ok': False, 'reason': 'Independent shared pip policy unavailable; no installation changed'}))
