from memory.dedup import build_fingerprint


def test_memory_fingerprint_not_empty():
    assert build_fingerprint("memory content")
