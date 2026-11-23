from io import BytesIO

from minio import Minio
from minio.error import MinioException, S3Error
from urllib3.exceptions import HTTPError

from app.application.import_export.ports import ObjectKey, ObjectStorageError


class MinioObjectStorage:
    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def put(self, key: ObjectKey, content: bytes, *, content_type: str) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                try:
                    self.client.make_bucket(self.bucket)
                except S3Error as error:
                    if error.code != "BucketAlreadyOwnedByYou":
                        raise
            self.client.put_object(self.bucket, key, BytesIO(content), len(content), content_type)
        except (MinioException, HTTPError) as error:
            raise ObjectStorageError("Не удалось сохранить файл") from error

    def get(self, key: ObjectKey) -> bytes | None:
        try:
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchBucket"}:
                return None
            raise ObjectStorageError("Не удалось прочитать файл") from error
        except (MinioException, HTTPError) as error:
            raise ObjectStorageError("Не удалось прочитать файл") from error

    def delete(self, key: ObjectKey) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except (MinioException, HTTPError) as error:
            raise ObjectStorageError("Не удалось удалить файл") from error
