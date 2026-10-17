"""Integration checks inside the build image with disposable /cache and /out volumes.

docker run --rm --mount type=bind,source=<repo>,target=/src,readonly \
  --mount type=volume,target=/cache --mount type=volume,target=/out \
  lucky65-firmware:local python /src/firmware/tests/test_build.py
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    assert not Path('/cache/modified').exists(), 'Use a disposable /cache volume'
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        for directory in ('firmware', 'vendor'):
            shutil.copytree(Path('/src') / directory, repo / directory)
        log = repo / 'build.log'

        def run(command, success=True, env=None):
            with log.open('w') as output:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, env=env)
            if (result.returncode == 0) != success:
                raise AssertionError(log.read_text()[-12000:])

        def build(stock=False, clean=False, success=True):
            script = 'build-stock.sh' if stock else 'build.sh'
            run(['bash', str(repo / 'firmware' / script)] + (['--clean'] if clean else []), success)
            if success:
                target = 'stock' if stock else 'modified'
                out = Path('/out') / target
                metadata = json.loads((out / 'metadata.json').read_text())
                assert metadata['target'] == target
                for name, digest in metadata['artifacts'].items():
                    assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest

        build()
        build(stock=True)
        print('PASS: both targets and artifact hashes', flush=True)
        tree = Path('/cache/modified/qmk')
        sentinel = tree / '.build/incremental-sentinel'
        sentinel.touch()
        build()
        assert sentinel.exists(), 'Unchanged inputs unexpectedly cleaned the build'
        stock_sentinel = Path('/cache/stock/qmk/.build/stock-sentinel')
        stock_sentinel.touch()
        build(clean=True)
        assert not sentinel.exists() and stock_sentinel.exists()
        print('PASS: incremental reuse and clean isolation', flush=True)

        source = repo / 'firmware/keyboards/lucky65v2/music_viz.c'
        original = source.read_bytes()
        extra = source.with_name('sync-test.h')
        extra.write_text('// deletion regression\n')
        source.write_bytes(original + b'\n// content sync regression\n')
        os.utime(source, (1, 1))
        build()
        staged = tree / 'keyboards/lucky65v2'
        assert (staged / source.name).read_bytes() == source.read_bytes()
        assert (staged / extra.name).exists()
        extra.unlink()
        source.write_bytes(original)
        os.utime(source, (1, 1))
        build()
        assert (staged / source.name).read_bytes() == original
        assert not (staged / extra.name).exists()
        print('PASS: older-timestamp change, deletion and revert', flush=True)

        run(['bash', str(repo / 'firmware/check-symbols.sh'), '/out/stock/lucky65v2_via_stock.elf'], False)
        source.write_bytes(original + b'\n#error deliberate_build_failure\n')
        build(success=False)
        assert not Path('/out/modified/metadata.json').exists()
        assert not Path('/out/modified/lucky65v2_via.bin').exists()
        assert stock_sentinel.exists()
        print('PASS: missing symbols and compiler failures propagate', flush=True)

        env = dict(os.environ, QMK_TREE='/opt/qmk')
        run(['bash', str(repo / 'firmware/setup.sh')], env=env)
        (repo / 'firmware/patches/9999-invalid.patch').write_text('not a patch\n')
        run(['bash', str(repo / 'firmware/setup.sh')], False, env)
        print('PASS: applied patches verified; invalid patch rejected', flush=True)


if __name__ == '__main__':
    main()
