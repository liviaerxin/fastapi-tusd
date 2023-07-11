from enum import Enum
from fastapi import FastAPI, Header, Request, HTTPException, params
from fastapi.routing import APIRoute, APIRouter
from starlette.requests import ClientDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from typing import Annotated, Union, Any, Hashable
import base64
import hashlib
from uuid import uuid4
from datetime import datetime, timedelta
import os

from typing import Dict, List, Optional, Union, Sequence

from .filestore import FileInfo, FileStore


class TusRouter(APIRouter):
    tus_version = "1.0.0"
    tus_extension = (
        "creation,creation-defer-length,creation-with-upload,expiration,termination"
    )
    tus_checksum_algorithm = "md5,sha1,crc32"

    def __init__(
        self,
        store_dir: str,
        max_size: int = 128849018880,
        prefix: str = "/files",
        *args,
        **kwargs,
    ):
        super().__init__(prefix=prefix, *args, **kwargs)

        self.store_dir = store_dir
        self.max_size = max_size
        # TODO: support s3
        self.datastore = FileStore(path=store_dir)

        self.location = self.prefix

        self.add_core_routes()

    def add_core_routes(self):
        @self.options("")
        # read information about server configuration
        async def read_server_config(request: Request, response: Response) -> Response:
            response.headers["Tus-Resumable"] = TusRouter.tus_version
            response.headers[
                "Tus-Checksum-Algorithm"
            ] = TusRouter.tus_checksum_algorithm
            response.headers["Tus-Version"] = TusRouter.tus_version
            response.headers["Tus-Max-Size"] = str(self.max_size)
            response.headers["Tus-Extension"] = TusRouter.tus_extension

            return response

        # creates a new file upload using the datastore after validating the length and parsing the metadata.
        @self.post("")
        async def post_file(
            request: Request,
            response: Response,
            upload_metadata: str = Header(None),
            upload_length: int = Header(None),
            upload_defer_length: int = Header(None),
            content_length: int = Header(None),
            content_type: str = Header(None),
        ):
            # Validate the request
            # upload_defer_length must be 1 if exists
            if upload_defer_length is not None and upload_defer_length != 1:
                raise HTTPException(
                    status_code=400,
                    detail="Upload-Defer-Length Must be not set or set as 1!",
                )

            if upload_length is None and upload_defer_length is None:
                raise HTTPException(
                    status_code=400,
                    detail="Upload-Defer-Length Must set as 1 because no Upload-Length specified!",
                )

            if upload_length is not None and upload_length > 0:
                is_size_deferred = False
            else:
                is_size_deferred = True

            # Parse the metadata
            metadata = {}
            if upload_metadata is not None and upload_metadata != "":
                # Decode the base64-encoded string
                for kv in upload_metadata.split(","):
                    key, value = kv.rsplit(" ", 1)
                    decoded_value = base64.b64decode(value.strip()).decode("utf-8")
                    metadata[key.strip()] = decoded_value

            uuid = str(uuid4().hex)

            info = FileInfo(
                uuid=uuid,
                offset=0,
                size=upload_length,
                is_size_deferred=is_size_deferred,
                storage={},
                metadata=metadata,
                expires=None,
            )

            self.datastore.write_file_info(info)
            self.datastore.new_file_bin(uuid=uuid)

            # Create a new file upload in datastore

            # Creation With Upload, similar with `PATCH` request
            if (
                content_length
                and content_length
                and upload_length
                and not is_size_deferred
            ):
                if not content_type == "application/offset+octet-stream":
                    raise HTTPException(
                        status_code=400,
                        detail="Content-Type Must be application/offset+octet-stream!",
                    )

                info = await _write_chunk(request, info)

                if not info:
                    response.status_code = 412
                    response.headers["Tus-Resumable"] = TusRouter.tus_version
                    return

                date_expiry = datetime.now() + timedelta(days=1)
                info.expires = str(date_expiry.isoformat())

                self.datastore.write_file_info(info)

                response.headers["Location"] = f"{self.location}/{uuid}"
                response.headers["Tus-Resumable"] = TusRouter.tus_version
                response.headers["Upload-Offset"] = str(info.offset)
                response.headers["Upload-Expires"] = str(info.expires)
                response.status_code = 204

                return response

            # Creation Without Upload
            else:
                response.headers["Location"] = f"{self.location}/{uuid}"
                response.headers["Tus-Resumable"] = TusRouter.tus_version

                response.status_code = 201
                return response

        @self.head("/{uuid}")
        # returns the length and offset for the HEAD request
        async def head_file(
            request: Request,
            response: Response,
            uuid: str,
        ):
            # check file exist
            # get info
            info = self.datastore.read_file_info(uuid=uuid)

            if info is None:
                raise HTTPException(status_code=404)

            response.headers["Tus-Resumable"] = TusRouter.tus_version
            response.headers["Upload-Length"] = str(info.size)
            response.headers["Upload-Offset"] = str(info.offset)
            response.headers["Cache-Control"] = "no-store"

            if info.is_size_deferred:
                response.headers["Upload-Defer-Length"] = str(1)

            # Encode str to base64
            if info.metadata:
                metadata_base64 = ""
                for key, value in info.metadata.items():
                    metadata_base64 += (
                        f"{key} {base64.b64encode(bytes(value, 'utf-8'))},"
                    )
                response.headers["Upload-Metadata"] = metadata_base64.strip(",")

            response.status_code = 200
            return response

        @self.patch("/{uuid}")
        # adds chunks to the upload
        async def patch_file(
            request: Request,
            response: Response,
            uuid: str,
            tus_resumable: str = Header(None),
            content_length: int = Header(None),
            content_type: str = Header(None),
            upload_offset: int = Header(None),
            upload_length: int = Header(None),
        ):
            # validate the request
            # write chunk to upload file
            # return response with headers

            if tus_resumable != TusRouter.tus_version:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Tus-Resumable!",
                )
            if content_type != "application/offset+octet-stream":
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Content-Type!",
                )

            # a non-existent resource
            info = self.datastore.read_file_info(uuid)
            if info is None:
                response.status_code = 404
                response.headers["Tus-Resumable"] = TusRouter.tus_version
                return response

            if info.is_size_deferred:
                if upload_length is None:
                    response.status_code = 412
                    response.headers["Tus-Resumable"] = TusRouter.tus_version
                    return response

                if not info.size and upload_length:
                    info.size = upload_length
                    self.datastore.write_file_info(info)

            lock = self.datastore.new_lock(uuid)

            with lock:
                # The Upload-Offset header's value MUST be equal to the current offset of the resource.
                if upload_offset != info.offset:
                    response.status_code = 409
                    response.headers["Tus-Resumable"] = TusRouter.tus_version
                    return

                # Saving
                info = await _write_chunk(request, info)

            # Post check actual file size
            if upload_offset + content_length != info.offset:
                print(f"disconnect with client")
                response.status_code = 460
                response.headers["Tus-Resumable"] = TusRouter.tus_version
                return response

            date_expiry = datetime.now() + timedelta(days=1)
            info.expires = str(date_expiry.isoformat())

            self.datastore.write_file_info(info)

            # Upload file complete
            if info.size == info.offset:
                # TODO: callbacks should be here
                pass

            response.headers["Location"] = f"{self.location}/{uuid}"
            response.headers["Tus-Resumable"] = TusRouter.tus_version
            response.headers["Upload-Offset"] = str(info.offset)
            response.headers["Upload-Expires"] = str(info.expires)
            response.status_code = 204
            pass

        @self.delete("/{uuid}")
        async def delete_file(request: Request, response: Response, uuid: str):
            lock = self.datastore.new_lock(uuid=uuid)

            with lock:
                self.datastore.delete_file_info(uuid=uuid)

            response.status_code = 204
            return response

        @self.get("/{uuid}")
        async def get_file(request: Request, response: Response, uuid: str):
            info = self.datastore.read_file_info(uuid=uuid)

            def read_file():
                f = self.datastore.open(uuid=uuid, mode="rb")
                yield from f

            return StreamingResponse(read_file(), media_type="video/mp4")

        async def _write_chunk(request: Request, info: FileInfo) -> FileInfo:
            f = self.datastore.open(info.uuid)

            try:
                async for chunk in request.stream():
                    chunk_size = len(chunk)
                    f.write(chunk)
                    info.offset += chunk_size
                    # info.chunk_size = chunk_size
                    # info.part += 1
            except ClientDisconnect as e:
                print(f"Client disconnected: {e}")
            finally:
                self.datastore.write_file_info(info)
                f.close()

            return info
