import json

from app.transcriber import bcut as bcut_module
from app.transcriber.bcut import BcutTranscriber


class _FakeResp:
    def __init__(self, payload=None, etag=""):
        self._payload = payload or {}
        self.headers = {"Etag": etag}
        self.url = ""

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """模拟必剪上传三步接口：申请上传 / PUT 分片 / 提交合并"""

    def __init__(self, per_size, upload_urls_count):
        self.per_size = per_size
        self.upload_urls_count = upload_urls_count
        self.commit_payloads = []

    def post(self, url, data=None, headers=None, timeout=None):
        if url == bcut_module.API_REQ_UPLOAD:
            body = json.loads(data)
            return _FakeResp({
                "data": {
                    "in_boss_key": "boss",
                    "resource_id": "res",
                    "upload_id": "up",
                    "upload_urls": [f"http://fake/{i}" for i in range(self.upload_urls_count)],
                    "per_size": self.per_size,
                    "size": body["size"],
                }
            })
        if url == bcut_module.API_COMMIT_UPLOAD:
            self.commit_payloads.append(json.loads(data))
            return _FakeResp({"code": 0, "data": {"download_url": "http://fake/dl"}})
        raise AssertionError(f"unexpected post: {url}")

    def put(self, url, data=None, headers=None):
        return _FakeResp(etag=f"etag-{url[-1]}")


def _upload_file(transcriber, tmp_path, name, content, chunks):
    f = tmp_path / name
    f.write_bytes(content)
    transcriber.session = _FakeSession(per_size=5, upload_urls_count=chunks)
    transcriber._upload(str(f))
    return transcriber.session.commit_payloads


def test_second_upload_commits_only_its_own_etags(tmp_path):
    t = BcutTranscriber()

    # 第一次：3 字节，1 分片
    commits = _upload_file(t, tmp_path, "a.mp3", b"aaa", chunks=1)
    assert len(commits[0]["Etags"].split(",")) == 1

    # 第二次（同一实例）：8 字节，2 分片——修复前会提交 3 个 etag
    commits = _upload_file(t, tmp_path, "b.mp3", b"aaaaaaaa", chunks=2)
    assert len(commits[0]["Etags"].split(",")) == 2


def test_first_upload_unchanged(tmp_path):
    t = BcutTranscriber()
    commits = _upload_file(t, tmp_path, "a.mp3", b"aaa", chunks=1)
    assert commits[0]["Etags"] == "etag-0"
    assert commits[0]["UploadId"] == "up"
