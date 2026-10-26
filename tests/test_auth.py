# 2026-10-26 20:07 KST
from auth import hash_password, verify_password, is_admin_login


def test_hash_is_not_plaintext():
    hashed = hash_password("1234")
    assert hashed != "1234"


def test_verify_correct_password():
    hashed = hash_password("1234")
    assert verify_password("1234", hashed) is True


def test_verify_wrong_password_rejected():
    hashed = hash_password("1234")
    assert verify_password("wrong", hashed) is False


def test_is_admin_login():
    assert is_admin_login("admin") is True
    assert is_admin_login("2026301") is False
