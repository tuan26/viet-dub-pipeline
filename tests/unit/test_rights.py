import pytest

from vietdub.models import VietdubError
from vietdub.rights import check_rights


def test_accepts_declared_rights():
    r = check_rights("CC-BY", "https://example.org/v", "Jane Doe")
    assert r.license == "cc-by"
    assert "Jane Doe" in r.credits()


@pytest.mark.parametrize(
    "license, source, attribution",
    [
        (None, "x", None),            # nothing declared
        ("cc-by-nc", "x", "a"),       # non-commercial
        ("cc-by-nd", "x", "a"),       # no derivatives
        ("found-online", "x", None),  # not a recognised basis
        ("owned", "", None),          # no source
        ("cc-by", "x", None),         # attribution required
    ],
)
def test_rejects(license, source, attribution):
    with pytest.raises(VietdubError):
        check_rights(license, source, attribution)
