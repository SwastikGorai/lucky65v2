"""Compile and run actual firmware logic against a tiny QMK hardware stub."""
from pathlib import Path
import os
import subprocess
import tempfile

here = Path(__file__).resolve().parent
keymap = (here / '../keyboards/lucky65v2/keymaps/via/keymap.c').read_text(encoding='utf-8')
# Compile the actual shortcut preamble, without unrelated vendor keymap hooks.
shortcut = keymap.split('bool im_process_record_user(', 1)[1].split('    switch (keycode)', 1)[0]
assert keymap.count('RGB_MOD, KC_DEL,') == 4
assert 'RGB_MOD, MUV_CYC,' not in keymap
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / 'shortcut.h').write_text('bool im_process_record_user(' + shortcut + 'return true;\n}\n')
    exe = tmp / ('test.exe' if os.name == 'nt' else 'test')
    subprocess.run([os.environ.get('CC', 'gcc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-I', str(here), '-I', str(tmp), str(here / 'test_music_viz.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
