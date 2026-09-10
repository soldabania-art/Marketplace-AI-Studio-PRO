from app.mfa_service import (
    consume_recovery_code,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_secret,
    totp_code,
    verify_totp,
)


def test_totp_verification_allows_only_the_adjacent_time_window():
    secret = "JBSWY3DPEHPK3PXP"
    code = totp_code(secret, at_time=1_700_000_000)
    assert verify_totp(secret, code, at_time=1_700_000_000)
    assert verify_totp(secret, code, at_time=1_700_000_030)
    assert not verify_totp(secret, code, at_time=1_700_000_090)
    assert not verify_totp(secret, "abcdef", at_time=1_700_000_000)


def test_mfa_secret_is_encrypted_and_recovery_code_is_consumed_once():
    secret = generate_secret()
    ciphertext = encrypt_secret(secret)
    assert secret not in ciphertext
    assert decrypt_secret(ciphertext) == secret
    raw_codes, hashes = generate_recovery_codes(2)
    remaining = consume_recovery_code(hashes, raw_codes[0].lower())
    assert remaining is not None and len(remaining) == 1
    assert consume_recovery_code(remaining, raw_codes[0]) is None
