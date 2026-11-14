from agent_receipts.redact import Redactor

LEAKS = [
    "export OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456",
    "git remote add o https://ghp_abcdefghijklmnopqrstuvwxyz0123456789@github.com/x/y",
    "aws configure set aws_access_key_id AKIAABCDEFGHIJKLMNOP",
    "curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnop' https://api",
    "password=hunter2hunter2",
    "token: Zx8Qp2Lm9Rt4Vb7Nc1Kd6Hs3Jf0Gw5Ye8Ua2Io",
]
SECRETS = ["sk-proj-abc", "ghp_abc", "AKIAABCD", "eyJhbGciOiJIUzI1NiJ9", "hunter2", "Zx8Qp2Lm9"]


def test_no_leaks() -> None:
    r = Redactor()
    for text, secret in zip(LEAKS, SECRETS, strict=True):
        out = r.text(text) or ""
        assert secret not in out, out
        assert "[REDACTED]" in out


def test_home_paths_and_truncation() -> None:
    r = Redactor(max_chars=20)
    out = r.text("/home/alice/projects/app/src/very/long/path.py") or ""
    assert "alice" not in out and out.startswith("~") and "chars]" in out


def test_extra_pattern() -> None:
    assert "ACME" not in (Redactor([r"ACME_[A-Z0-9]{8}"]).text("key ACME_12345678") or "")
