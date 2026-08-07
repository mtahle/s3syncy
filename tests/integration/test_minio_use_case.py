import os
import shutil
import subprocess
import time

import boto3
import pytest
import yaml
from botocore.exceptions import ClientError
from moto import mock_aws

from s3syncy.config import load_config
from s3syncy.engine import SyncEngine
from s3syncy.index import SyncIndex
from s3syncy.patterns import ExclusionFilter


@pytest.fixture(scope="module")
def minio_service():
    bucket = "test-bucket"
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
    host = "127.0.0.1"
    port = 9000
    endpoint = f"http://{host}:{port}"
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    endpoint_url = os.environ.get("MINIO_ENDPOINT_URL")
    if endpoint_url:
        try:
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            client.list_buckets()
        except Exception as exc:
            raise RuntimeError(f"Configured MinIO endpoint is not reachable: {endpoint_url}") from exc
        try:
            client.create_bucket(Bucket=bucket)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "BucketAlreadyOwnedByYou":
                raise
        yield endpoint_url, access_key, secret_key, bucket
        return

    docker_available = shutil.which("docker") is not None
    if docker_available:
        container_name = "s3syncy-minio-test"
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-p",
                    f"{port}:9000",
                    "-e",
                    f"MINIO_ROOT_USER={access_key}",
                    "-e",
                    f"MINIO_ROOT_PASSWORD={secret_key}",
                    "minio/minio:RELEASE.2024-10-02T17-50-41Z",
                    "server",
                    "/data",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(40):
                try:
                    client = boto3.client(
                        "s3",
                        endpoint_url=endpoint,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        region_name=region,
                    )
                    client.list_buckets()
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError("MinIO did not become ready")

            client.create_bucket(Bucket=bucket)
            yield endpoint, access_key, secret_key, bucket
        finally:
            subprocess.run(["docker", "rm", "-f", container_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    with mock_aws():
        client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        client.create_bucket(Bucket=bucket)
        yield endpoint, access_key, secret_key, bucket


@pytest.fixture()
def temp_sync_env(tmp_path, minio_service):
    endpoint, access_key, secret_key, bucket = minio_service
    sync_dir = tmp_path / "sync"
    sync_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "sync_dirs": [str(sync_dir)],
                "s3": {
                    "bucket": bucket,
                    "region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
                    "endpoint_url": endpoint,
                    "profile": "",
                },
                "threads": 2,
                "scan_interval_seconds": 30,
                "bandwidth": {"upload_limit_mbps": 0, "download_limit_mbps": 0},
                "conflict": {"strategy": "newest_wins", "backup_before_overwrite": True},
                "integrity": {"enabled": False, "algorithm": "md5", "on_failure": "warn", "max_retries": 1},
                "resources": {"max_memory_mb": 256, "chunk_size_mb": 5},
                "logging": {"level": "INFO", "file": str(tmp_path / "s3syncy.log"), "max_size_mb": 10, "backup_count": 1},
                "exclude_file": ".syncignore",
            }
        ),
        encoding="utf-8",
    )
    (sync_dir / "hello.txt").write_text("hello from s3syncy\n", encoding="utf-8")
    (sync_dir / "nested").mkdir()
    (sync_dir / "nested" / "report.txt").write_text("nested content\n", encoding="utf-8")
    os.environ["AWS_ACCESS_KEY_ID"] = access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    cfg = load_config(config_path)
    index_path = tmp_path / ".s3syncy_index.db"
    index = SyncIndex(index_path)
    exclusion = ExclusionFilter(cfg.exclude_file)
    engine = SyncEngine(cfg, index, exclusion)
    return {
        "cfg": cfg,
        "index": index,
        "engine": engine,
        "config_path": config_path,
        "sync_dir": sync_dir,
        "tmp_path": tmp_path,
        "bucket": bucket,
        "endpoint": endpoint,
    }


def test_minio_use_case_upload_list_search_pull(temp_sync_env):
    index = temp_sync_env["index"]
    engine = temp_sync_env["engine"]
    tmp_path = temp_sync_env["tmp_path"]

    engine.full_scan()
    assert index.stats()["synced"] >= 2

    records = index.list_folder("nested", limit=10)
    assert any(record.rel_path == "nested/report.txt" for record in records)

    search_results = index.search("report", limit=10)
    assert any(result.rel_path == "nested/report.txt" for result in search_results)

    pull_dest = tmp_path / "pulled"
    ok = engine.pull_file("nested/report.txt", pull_dest)
    assert ok is True
    assert pull_dest.read_text(encoding="utf-8") == "nested content\n"

    assert (tmp_path / "pulled").exists()

    client = boto3.client(
        "s3",
        endpoint_url=temp_sync_env["endpoint"],
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    paginator = client.get_paginator("list_objects_v2")
    objects = paginator.paginate(Bucket=temp_sync_env["bucket"])
    keys = [obj["Key"] for page in objects for obj in page.get("Contents", [])]
    assert any(key.endswith("hello.txt") for key in keys)
    assert any(key.endswith("nested/report.txt") for key in keys)

    index.close()
    engine.shutdown()
