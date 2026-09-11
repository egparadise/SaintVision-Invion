"""Copy CI's installed Git and its ELF libraries into the synthetic image.

No downloads, user repository or credentials. Invoked only on the Linux CI runner;
the resulting image digest is pinned by the existing test admission fixture.
"""

from pathlib import Path
import shutil
import subprocess
import sys

target = Path(sys.argv[1]).resolve()
assert target.is_dir() and target.name == "node-image"
binary = Path("/usr/bin/git")
assert binary.is_file()
result = subprocess.run(["ldd", str(binary)], capture_output=True, text=True, check=True)
paths = {binary}
for line in result.stdout.splitlines():
    for word in line.split():
        if word.startswith("/"):
            paths.add(Path(word))
for source in paths:
    assert source.is_absolute() and source.is_file() and ".." not in source.parts
    destination = target / "git-root" / source.relative_to("/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755)
print("Prepared synthetic Git runtime and", len(paths) - 1, "libraries")
