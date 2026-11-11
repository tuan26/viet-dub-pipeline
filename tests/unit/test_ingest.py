import json

import pytest

from vietdub import cli
from vietdub.ingest import archive, channels, commons, fetch, ytdlp
from vietdub.ingest.catalog import Catalog, Item
from vietdub.models import VietdubError

# Shape copied from a real archive.org advancedsearch response.
ARCHIVE = {"response": {"docs": [
    {"identifier": "flag-of-botswana", "title": "Flag of Botswana", "creator": "Alucard",
     "language": "eng", "licenseurl": "http://creativecommons.org/publicdomain/zero/1.0/"},
    {"identifier": "nc-film", "title": "NC", "creator": "X",
     "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/"},
    {"identifier": "by-no-author", "title": "Anon",
     "licenseurl": "https://creativecommons.org/licenses/by/4.0/"},
    {"identifier": "by-film", "title": ["By film"], "creator": ["Jane", "Joe"],
     "licenseurl": "https://creativecommons.org/licenses/by/4.0/"},
]}}
ARCHIVE_FILES = {"files": [
    {"name": "Flag of Botswana.ia.mp4", "source": "derivative", "size": "26854791"},
    {"name": "Flag of Botswana (Dark).mp4", "source": "original", "size": "10081020"},
    {"name": "Flag of Botswana.mp4", "source": "original", "size": "26854811"},
    {"name": "__ia_thumb.jpg", "source": "original", "size": "2692"},
]}
COMMONS = {"query": {"pages": {
    "1": {"pageid": 1, "title": "File:Good.webm", "imageinfo": [{
        "url": "https://upload.wikimedia.org/good.webm",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Good.webm",
        "extmetadata": {"License": {"value": "cc-by-sa-4.0"},
                        "Artist": {"value": '<a href="//x">Jane  Doe</a>'}}}]},
    "2": {"pageid": 2, "title": "File:Unknown.webm", "imageinfo": [{
        "url": "https://upload.wikimedia.org/u.webm", "extmetadata": {}}]},
}}}


def test_archive_keeps_only_usable_licences_with_required_credit():
    items = archive.search("flag", 10, lambda url, params: ARCHIVE)
    assert [(i.id, i.license, i.attribution) for i in items] == [
        ("archive:flag-of-botswana", "cc0", "Alucard"),
        ("archive:by-film", "cc-by", "Jane"),
    ]


def test_archive_picks_largest_original_video():
    item = Item("archive:flag-of-botswana", "archive", "t", "u", "cc0")
    url = archive.resolve_download(item, lambda url, params: ARCHIVE_FILES)
    assert url == "https://archive.org/download/flag-of-botswana/Flag%20of%20Botswana.mp4"


def test_commons_reads_licence_and_strips_artist_markup():
    items = commons.search("x", 10, lambda url, params: COMMONS)
    assert [(i.id, i.license, i.attribution, i.download_url) for i in items] == [
        ("commons:1", "cc-by-sa", "Jane Doe", "https://upload.wikimedia.org/good.webm")
    ]


def test_youtube_drops_standard_licence():
    lines = [
        {"id": "a", "title": "CC", "channel": "Chan", "license": "Creative Commons Attribution license (reuse allowed)"},
        {"id": "b", "title": "Std", "channel": "Chan", "license": None},
        {"id": "c", "title": "Std2", "channel": "Chan", "license": "Standard YouTube License"},
    ]
    items = ytdlp.search_youtube_cc("q", 5, lambda args: "\n".join(map(json.dumps, lines)))
    assert [i.id for i in items] == ["youtube:a"]


def test_catalog_dedups_and_persists(tmp_path):
    cat = Catalog(tmp_path)
    assert cat.add(Item("archive:x", "archive", "T", "u", "cc0"))
    assert not cat.add(Item("archive:x", "archive", "Other", "u", "cc0"))
    cat.save()
    assert Catalog(tmp_path).get("archive:x").title == "T"


def _config(tmp_path, evidence="permissions/studio.pdf", **extra):
    fields = {"name": "Studio A", "url": "https://example.com/channel", "attribution": "Studio A",
              "permission": "Email 2026-11-01: cho phép dịch, lồng tiếng, phát hành tại VN",
              "evidence": evidence, **extra}
    body = "[[channel]]\n" + "\n".join(f'{k} = "{v}"' for k, v in fields.items() if v is not None)
    path = tmp_path / "sources.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_channel_without_evidence_file_is_refused(tmp_path):
    with pytest.raises(VietdubError, match="bằng chứng"):
        channels.load(_config(tmp_path))


def test_channel_without_permission_text_is_refused(tmp_path):
    with pytest.raises(VietdubError, match="permission"):
        channels.load(_config(tmp_path, permission=None))


def test_channel_sync_creates_approved_licensed_items(tmp_path):
    (tmp_path / "permissions").mkdir()
    (tmp_path / "permissions" / "studio.pdf").write_bytes(b"%PDF")
    channel = channels.load(_config(tmp_path, language="zh"))[0]
    out = "\n".join(json.dumps(e) for e in [
        {"id": "ep1", "title": "Tập 1", "url": "https://example.com/v/ep1"},
        {"id": "ep2", "title": "Tập 2", "url": "https://example.com/v/ep2"},
    ])
    items = channels.sync(channel, 20, lambda args: out)
    assert [(i.id, i.status, i.license) for i in items] == [
        ("channel:Studio A:ep1", "approved", "licensed"),
        ("channel:Studio A:ep2", "approved", "licensed"),
    ]
    assert "studio.pdf" in items[0].permission


def test_fetch_only_touches_approved_and_survives_failures(tmp_path):
    cat = Catalog(tmp_path)
    cat.add(Item("a:found", "archive", "t", "u", "cc0"))
    cat.add(Item("a:bad", "archive", "t", "u", "cc0", status="approved"))
    cat.add(Item("a:good", "archive", "t", "u", "cc0", status="approved"))

    def fake(item, library):
        if item.id == "a:bad":
            raise VietdubError("hỏng")
        return library / "videos" / "good.mp4"

    assert fetch.fetch_approved(cat, 10, fake, log=lambda m: None) == 1
    again = Catalog(tmp_path)
    assert {i.id: i.status for i in again.items.values()} == {
        "a:found": "found", "a:bad": "failed", "a:good": "fetched"}
    assert again.get("a:bad").error == "hỏng"


def test_cli_approve_then_list(tmp_path, capsys):
    cat = Catalog(tmp_path)
    cat.add(Item("archive:x", "archive", "T", "u", "cc0"))
    cat.save()
    assert cli.main(["ingest", "approve", "all", "--library", str(tmp_path)]) == 0
    assert Catalog(tmp_path).get("archive:x").status == "approved"
    assert cli.main(["ingest", "approve", "archive:x", "--library", str(tmp_path)]) == 2
    assert cli.main(["ingest", "list", "--library", str(tmp_path), "--status", "approved"]) == 0
    assert "archive:x" in capsys.readouterr().out


def test_failed_download_can_be_approved_again(tmp_path):
    cat = Catalog(tmp_path)
    cat.add(Item("archive:x", "archive", "T", "u", "cc0", status="failed", error="mạng"))
    cat.save()
    assert cli.main(["ingest", "approve", "archive:x", "--library", str(tmp_path)]) == 0
    assert Catalog(tmp_path).get("archive:x").status == "approved"
