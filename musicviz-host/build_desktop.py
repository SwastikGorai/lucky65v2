"""Build the portable Windows app with the locked build dependency group."""
from importlib import metadata
from pathlib import Path
import subprocess
import sys

from musicviz_gui import icon_image

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "build" / "desktop"


def main():
    if sys.platform != "win32":
        raise SystemExit("Build this Windows executable on Windows.")
    OUT.mkdir(parents=True, exist_ok=True)
    icon = OUT / "Lucky65Music.ico"
    icon_image().save(icon)
    notices = OUT / "THIRD_PARTY_NOTICES.txt"
    sections = [(ROOT.parent / "LICENSE").read_text(encoding="utf-8")]
    for dist in metadata.distributions():
        sections.append(f"\n{dist.metadata['Name']} {dist.version}\n")
        for file in dist.files or []:
            if "license" in str(file).lower() or "copying" in str(file).lower():
                path = Path(dist.locate_file(file))
                if path.is_file():
                    sections.append(path.read_text(encoding="utf-8", errors="replace"))
    sections.append(Path(sys.base_prefix, "LICENSE.txt").read_text(encoding="utf-8"))
    notices.write_text("\n".join(sections), encoding="utf-8")
    version = OUT / "version.txt"
    version.write_text('''VSVersionInfo(ffi=FixedFileInfo(filevers=(0,1,0,0), prodvers=(0,1,0,0),
mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)),
kids=[StringFileInfo([StringTable('040904B0', [StringStruct('ProductName','Lucky65 Music'),
StringStruct('FileDescription','Lucky65 Music desktop controller'),
StringStruct('FileVersion','0.1.0'), StringStruct('ProductVersion','0.1.0')])]),
VarFileInfo([VarStruct('Translation',[1033,1200])])])''', encoding="utf-8")
    mode = "--onedir" if "--onedir" in sys.argv else "--onefile"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    mode, "--windowed", "--name", "Lucky65Music", "--icon", str(icon),
                    "--version-file", str(version),
                    "--distpath", str(OUT / ("folder" if mode == "--onedir" else "release")),
                    "--workpath", str(OUT / "work"), "--specpath", str(OUT),
                    "--hidden-import", "_cffi_backend",
                    "--exclude-module", "textual",
                    "--add-data", f"{notices};.", str(ROOT / "musicviz_gui.py")], check=True)


if __name__ == "__main__":
    main()
