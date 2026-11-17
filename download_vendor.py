import hashlib
import urllib.request
from pathlib import Path

directory = Path(__file__).resolve().parent / "static" / "vendor"
directory.mkdir(parents=True, exist_ok=True)
assets = {
    "quill.js": ("https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.js", "f6157c72ac9b3f51cdead426335688a027b12405d9d6a4daadd38a676b2d7ff2"),
    "quill.snow.css": ("https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.snow.css", "1c7948cd13aa92fac6390319bc1e5e461823da171519d3a768db56164f871636"),
    "QUILL-LICENSE.txt": ("https://cdn.jsdelivr.net/npm/quill@2.0.3/LICENSE", "395c12b616d6f58238b4be39284d4d9221b58dd6e1f1e34d9ab537e34abbb022"),
    "docx.js": ("https://cdn.jsdelivr.net/npm/docx@9.15.4/dist/index.iife.min.js", "eb89473fb5b458fb9534573c5c442787666dd1e4f9a9b165fa6f4024385e45ae"),
    "DOCX-LICENSE.txt": ("https://raw.githubusercontent.com/dolanmiu/docx/master/LICENSE", "b5b2364c0c95a26b2a2399d7e706a61acac680be1d5b180b00592ee85830bffb"),
}
for filename, (url, expected_hash) in assets.items():
    with urllib.request.urlopen(url, timeout=30) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != expected_hash:
        raise RuntimeError("Unexpected asset checksum: " + filename)
    (directory / filename).write_bytes(content)
    print("Ready:", filename)
