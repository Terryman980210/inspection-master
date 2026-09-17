"""Local, atomic autosave snapshots bound to the exact drawing bytes."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from .models import InspectionCandidate, normalize_orders


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


class SessionStore:
    def __init__(self, root):
        self.root = Path(root)

    def identity(self, path):
        path = Path(path).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        key = hashlib.sha256((str(path) + '\n' + digest).encode()).hexdigest()
        return str(path), digest, key

    def restore(self, identity, fresh):
        path, digest, key = identity
        snapshot = self.root / (key + '.json')
        if not snapshot.exists(): return fresh, False
        data = json.loads(snapshot.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or data.get('drawing_path') != path or data.get('sha256') != digest:
            raise ValueError('自動保存データの形式が一致しません')
        saved = [InspectionCandidate.from_dict(c) for c in data['candidates']]
        # Reject incomplete/foreign snapshots instead of attaching edits to different entities.
        expected = {(c.id, c.source_handle) for c in fresh}
        if len(saved) != len(fresh) or {(c.id, c.source_handle) for c in saved} != expected:
            raise ValueError('自動保存データと抽出候補の対応が一致しません')
        normalize_orders(saved)
        return saved, True

    def save(self, identity, candidates):
        path, digest, key = identity
        normalize_orders(candidates)
        atomic_json(self.root / (key + '.json'), {
            'schema_version': 1, 'drawing_path': path, 'sha256': digest,
            'candidates': [c.to_dict() for c in candidates],
        })
        atomic_json(self.root / 'last.json', {'drawing_path': path})

    def last_path(self):
        p = self.root / 'last.json'
        return json.loads(p.read_text(encoding='utf-8'))['drawing_path'] if p.exists() else None
