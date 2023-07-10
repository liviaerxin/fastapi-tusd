from pydantic import BaseModel, Field
from typing import Annotated, Union, Any
from datetime import datetime
import os
import json
import sys
from filelock import FileLock


class FileInfo(BaseModel):
    uuid: str
    offset: int = 0
    is_deferred: bool
    storage: dict[str, str]
    upload_metadata: dict[str, str]
    upload_length: int = 0
    upload_part: int = 0
    upload_chunk_size: int = 0
    expires: str | None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FileStore(BaseModel):
    path: str

    def __init__(self, path: str, **kwargs) -> None:
        self._cache: dict[str, FileInfo] = {}

        if os.path.isfile(path):
            print(
                f"ERROR: The path[{path}] is not a valid folder. Please use a valid folder instead!"
            )

            # Exit to cancel project
            sys.exit(1)

        if not os.path.exists(path):
            os.mkdir(path)

        super.__init__(path=path, **kwargs)

    def is_existed(self, uuid: str) -> bool:
        if os.path.exists(self.file_bin_path(uuid)) or os.path.exists(
            self.file_info_path(uuid)
        ):
            return True
        else:
            return False

    def file_bin_path(self, uuid: str) -> str:
        return os.path.join(self.path, uuid)

    def file_info_path(self, uuid: str) -> str:
        return os.path.join(self.path, f"{uuid}.info")

    def read_file_info(self, uuid: str) -> FileInfo:
        # cache
        cached_info = self._cache.get(uuid)
        if cached_info:
            return cached_info

        fpath = self.file_info_path(uuid)
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                cached_info = FileInfo(**json.load(f))
                # cache
                self._cache[uuid] = cached_info
                return cached_info
        else:
            return None

    def write_file_info(self, info: FileInfo):
        fpath = self.file_info_path(info.uuid)
        info.storage = {"type": "filestore", "path": self.file_bin_path(info.uuid)}

        with open(fpath, "w") as f:
            f.write(info.model_dump_json(indent=2))

        # cache
        self._cache[info.uuid] = info

    def delete_file_info(self, uuid: str):
        if os.path.exists(self.file_info_path(uuid)):
            os.remove(self.file_info_path(uuid))
        if os.path.exists(self.file_bin_path(uuid)):
            os.remove(self.file_bin_path(uuid))
        if self._cache.get(uuid):
            del self._cache[uuid]
            
    def new_lock(self, uuid: str) -> FileLock:
        return FileLock(os.path.join(self.path, f"{uuid}.lock"), 10)