"""Folder watch: a file is analyzed once; failures stop after MAX_ATTEMPTS."""

import os
import time

from app.connectors import folder_watch
from app.connectors.folder_watch import ExtractedDocument, scan_once
from app.deps import get_repo
from app.schemas import LlmMeta, LlmMode


class FakeLlm:
    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    def extract_document(self, **kw):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return ExtractedDocument(doc_type="invoice", confidence=0.9, fields={"invoice_number": "123"}), LlmMeta(mode=LlmMode.live, model="m")


def _drop(folder, name, data=b"%PDF-1.4 x"):
    p = folder / name
    p.write_bytes(data)
    old = time.time() - 60
    os.utime(p, (old, old))  # past the settle window
    return p


def test_each_file_is_analyzed_once(client, tmp_path):
    folder_watch._failures.clear()
    repo, llm = get_repo(), FakeLlm()
    assert scan_once(tmp_path, repo, llm) == 0 and llm.calls == 0  # empty folder: no API call
    _drop(tmp_path, "a.pdf")
    assert scan_once(tmp_path, repo, llm) == 1 and llm.calls == 1
    assert scan_once(tmp_path, repo, llm) == 0 and llm.calls == 1  # unchanged file: not re-sent
    _drop(tmp_path, "b.pdf", b"%PDF-1.4 y")
    assert scan_once(tmp_path, repo, llm) == 1 and llm.calls == 2  # only the new file


def test_failing_file_stops_after_max_attempts(client, tmp_path):
    folder_watch._failures.clear()
    _drop(tmp_path, "bad.pdf")
    llm = FakeLlm(fail=True)
    for _ in range(folder_watch.MAX_ATTEMPTS + 3):
        scan_once(tmp_path, get_repo(), llm)
    assert llm.calls == folder_watch.MAX_ATTEMPTS
