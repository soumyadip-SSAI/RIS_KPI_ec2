"""Shared fixtures. fake_s3: an in-memory S3 (no AWS access needed) used instead of boto3."""
from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError

from ris_kpi.common import s3


class FakeS3:
    def __init__(self):
        self.objects = {}  # "bucket/key" -> bytes

    def put(self, uri, text):
        bucket, key = s3.split_s3_uri(uri)
        self.objects[f"{bucket}/{key}"] = text.encode()

    def get(self, uri):
        bucket, key = s3.split_s3_uri(uri)
        return self.objects[f"{bucket}/{key}"].decode()

    def _data(self, bucket, key, op):
        try:
            return self.objects[f"{bucket}/{key}"]
        except KeyError:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, op) from None

    def head_object(self, Bucket, Key):
        data = self._data(Bucket, Key, "HeadObject")
        return {"ContentLength": len(data), "LastModified": datetime(2026, 11, 17, 6, 30, tzinfo=timezone.utc)}

    def download_file(self, bucket, key, path):
        data = self._data(bucket, key, "GetObject")
        with open(path, "wb") as f:
            f.write(data)

    def upload_file(self, path, bucket, key):
        with open(path, "rb") as f:
            self.objects[f"{bucket}/{key}"] = f.read()


@pytest.fixture
def fake_s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(s3, "get_client", lambda: fake)
    return fake
