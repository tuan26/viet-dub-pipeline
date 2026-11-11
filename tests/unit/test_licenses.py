import pytest

from vietdub.ingest.licenses import normalize


@pytest.mark.parametrize("raw, expected", [
    ("http://creativecommons.org/publicdomain/zero/1.0/", "cc0"),
    ("https://creativecommons.org/publicdomain/mark/1.0/", "public-domain"),
    ("https://creativecommons.org/licenses/by/4.0/", "cc-by"),
    ("https://creativecommons.org/licenses/by-sa/3.0/", "cc-by-sa"),
    ("cc-by-sa-4.0", "cc-by-sa"),
    ("CC BY 3.0", "cc-by"),
    ("cc0", "cc0"),
    ("pd", "public-domain"),
    ("Public domain", "public-domain"),
    ("Creative Commons Attribution license (reuse allowed)", "cc-by"),
    # not usable for a dubbed, monetised re-release
    ("https://creativecommons.org/licenses/by-nc/4.0/", None),
    ("https://creativecommons.org/licenses/by-nd/4.0/", None),
    ("https://creativecommons.org/licenses/by-nc-sa/4.0/", None),
    ("CC BY-NC-ND 4.0", None),
    ("Standard YouTube License", None),
    ("All rights reserved", None),
    ("Fair use", None),
    ("", None),
    (None, None),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected
