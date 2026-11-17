import hashlib
import urllib.request
from pathlib import Path

directory = Path(__file__).resolve().parent / "static" / "vendor"
directory.mkdir(parents=True, exist_ok=True)
assets = {
    "quill.js": ("dist/quill.js", "f6157c72ac9b3f51cdead426335688a027b12405d9d6a4daadd38a676b2d7ff2"),
    "quill.snow.css": ("dist/quill.snow.css", "1c7948cd13aa92fac6390319bc1e5e461823da171519d3a768db56164f871636"),
    "QUILL-LICENSE.txt": ("LICENSE", "395c12b616d6f58238b4be39284d4d9221b58dd6e1f1e34d9ab537e34abbb022"),
}
for filename, (source, expected_hash) in assets.items():
    with urllib.request.urlopen("https://cdn.jsdelivr.net/npm/quill@2.0.3/" + source, timeout=30) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != expected_hash:
        raise RuntimeError("Unexpected asset checksum: " + filename)
    (directory / filename).write_bytes(content)
    print("Ready:", filename)
