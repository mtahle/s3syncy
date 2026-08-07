"""Unit tests for integrity module."""

import hashlib

from s3syncy.integrity import (
    compute_hash,
    s3_etag_matches,
    verify_upload,
)


class TestComputeHash:
    """Test file hashing functions."""

    def test_compute_hash_md5(self, tmp_path):
        """Test MD5 hash computation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = compute_hash(test_file, "md5")

        # Verify against known MD5
        expected = hashlib.md5(b"Hello, World!").hexdigest()
        assert result == expected

    def test_compute_hash_sha256(self, tmp_path):
        """Test SHA256 hash computation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = compute_hash(test_file, "sha256")

        # Verify against known SHA256
        expected = hashlib.sha256(b"Hello, World!").hexdigest()
        assert result == expected

    def test_compute_hash_large_file(self, tmp_path):
        """Test hashing a larger file (streaming)."""
        test_file = tmp_path / "large.bin"
        # Create a 1MB file
        data = b"x" * (1024 * 1024)
        test_file.write_bytes(data)

        result = compute_hash(test_file, "md5")
        expected = hashlib.md5(data).hexdigest()
        assert result == expected


class TestS3EtagMatches:
    """Test S3 ETag comparison logic."""

    def test_etag_matches_simple(self):
        """Test matching ETag for single-part upload."""
        local_hash = "5d41402abc4b2a76b9719d911017c592"
        s3_etag = '"5d41402abc4b2a76b9719d911017c592"'

        assert s3_etag_matches(local_hash, s3_etag) is True

    def test_etag_not_matches(self):
        """Test non-matching ETag."""
        local_hash = "5d41402abc4b2a76b9719d911017c592"
        s3_etag = '"different123456789abcdef"'

        assert s3_etag_matches(local_hash, s3_etag) is False

    def test_etag_multipart_optimistic(self):
        """Test multipart ETag returns True optimistically."""
        local_hash = "5d41402abc4b2a76b9719d911017c592"
        s3_etag = '"5d41402abc4b2a76b9719d911017c592-2"'  # -2 indicates multipart

        # Should return True for multipart (can't verify)
        assert s3_etag_matches(local_hash, s3_etag) is True

    def test_etag_unquoted(self):
        """Test ETag without quotes."""
        local_hash = "5d41402abc4b2a76b9719d911017c592"
        s3_etag = "5d41402abc4b2a76b9719d911017c592"

        assert s3_etag_matches(local_hash, s3_etag) is True


class TestVerifyUpload:
    """Test upload verification."""

    def test_verify_upload_md5_success(self, tmp_path):
        """Test successful MD5 verification."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        expected_hash = hashlib.md5(b"Hello, World!").hexdigest()
        s3_head = {"ETag": f'"{expected_hash}"'}

        result = verify_upload(test_file, s3_head, "md5")
        assert result is True

    def test_verify_upload_md5_failure(self, tmp_path):
        """Test failed MD5 verification."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        s3_head = {"ETag": '"wronghash123456789"'}

        result = verify_upload(test_file, s3_head, "md5")
        assert result is False

    def test_verify_upload_sha256_success(self, tmp_path):
        """Test successful SHA256 verification."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        expected_hash = hashlib.sha256(b"Hello, World!").hexdigest()
        s3_head = {"ChecksumSHA256": expected_hash}

        result = verify_upload(test_file, s3_head, "sha256")
        assert result is True

    def test_verify_upload_sha256_missing(self, tmp_path):
        """Test SHA256 verification when checksum is missing."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        s3_head = {}  # No ChecksumSHA256

        # Should return True (skip verification)
        result = verify_upload(test_file, s3_head, "sha256")
        assert result is True
