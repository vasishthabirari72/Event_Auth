"""One-time provisioning of owner-approved models; no runtime network dependency."""

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


def fetch(url: str) -> bytes:
    with urlopen(
        Request(url, headers={"User-Agent": "event-auth-model-setup"}), timeout=120
    ) as response:
        return response.read()


def main() -> None:
    target = Path("assets/models")
    target.mkdir(parents=True, exist_ok=True)
    manifest_file = target / "manifest.json"
    if manifest_file.exists():
        commit = json.loads(manifest_file.read_text())["commit"]
    else:
        commit = json.loads(fetch("https://api.github.com/repos/opencv/opencv_zoo/commits/main"))[
            "sha"
        ]
    files = {
        "sface.onnx": "models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "yunet.onnx": "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    }
    manifest = {"repository": "https://github.com/opencv/opencv_zoo", "commit": commit, "files": {}}
    for local, remote in files.items():
        # Git LFS pointer records the publisher's exact expected digest and size.
        pointer = fetch(
            f"https://raw.githubusercontent.com/opencv/opencv_zoo/{commit}/{remote}"
        ).decode()
        lines = dict(line.split(" ", 1) for line in pointer.strip().splitlines())
        expected = lines["oid"].removeprefix("sha256:")
        data = fetch(
            f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{commit}/{remote}"
        )
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected or len(data) != int(lines["size"]):
            raise RuntimeError("Model integrity check failed")
        (target / local).write_bytes(data)
        license_path = str(Path(remote).parent / "LICENSE")
        (target / (local + ".LICENSE")).write_bytes(
            fetch(f"https://raw.githubusercontent.com/opencv/opencv_zoo/{commit}/{license_path}")
        )
        manifest["files"][local] = {"source_path": remote, "sha256": digest, "bytes": len(data)}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Verified SFace and YuNet model files provisioned locally.")


if __name__ == "__main__":
    main()
