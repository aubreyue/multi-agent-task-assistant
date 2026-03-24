from memory.dedup import build_fingerprint, is_near_duplicate


def test_fingerprint_is_stable():
    assert build_fingerprint("Hello  World") == build_fingerprint("hello world")


def test_near_duplicate():
    assert is_near_duplicate("agent runtime memory layer", "agent runtime memory layer")
