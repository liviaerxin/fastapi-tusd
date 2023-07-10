from fastapi import FastAPI, Header, Request, HTTPException, APIRouter
from starlette.requests import ClientDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from typing import Annotated, Union, Any, Hashable
import base64
import hashlib
from uuid import uuid4
from datetime import datetime, timedelta
import os

from .schemas import FileInfo, FileStore

router = APIRouter()

tus_version = "1.0.0"
tus_extension = (
    "creation,creation-defer-length,creation-with-upload,expiration,termination"
)
tus_checksum_algorithm = "md5,sha1,crc32"
max_size = 128849018880
location = "http://127.0.0.1:8000/files"
files_dir = "/tmp/files"

FS = FileStore(path=files_dir)


@router.post("/files")
async def create_upload_resource(
    request: Request,
    response: Response,
    upload_metadata: str = Header(None),
    upload_length: int = Header(None),
    upload_defer_length: int = Header(None),
    content_length: int = Header(None),
    content_type: str = Header(None),
):
    if upload_defer_length is not None and upload_defer_length != 1:
        raise HTTPException(status_code=400, detail="Invalid Upload-Defer-Length")

    if upload_length is None and upload_defer_length is None:
        raise HTTPException(status_code=400, detail="Invalid Upload-Defer-Length")

    if upload_length is not None and upload_length > 0:
        defer_length = False
    else:
        defer_length = True

    # Create a new upload and store the file and metadata in the mapping
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
        is_deferred=defer_length,
        storage=None,
        upload_metadata=metadata,
        upload_length=upload_length,
        expires=None,
    )

    FS.write_file_info(info)

    # Create the empty file
    open(os.path.join(files_dir, f"{uuid}"), "a").close()

    # Creation With Upload, similar with `PATCH` request
    if content_length and content_length and upload_length and not defer_length:
        assert content_type == "application/offset+octet-stream"

        info = await _save_request_stream(request, uuid)

        if not info:
            response.status_code = 412
            response.headers["Tus-Resumable"] = tus_version
            return

        date_expiry = datetime.now() + timedelta(days=1)
        info.expires = str(date_expiry.isoformat())
        
        FS.write_file_info(info)

        response.headers["Location"] = f"{location}/{uuid}"
        response.headers["Tus-Resumable"] = tus_version
        response.headers["Upload-Offset"] = str(info.offset)
        response.headers["Upload-Expires"] = str(info.expires)
        response.status_code = 204

        return response

    # Creation Without Upload
    else:
        response.headers["Location"] = f"{location}/{uuid}"
        response.headers["Tus-Resumable"] = tus_version

        response.status_code = 201
        return response


@router.head("/files/{uuid}")
async def read_file_meta(request: Request, response: Response, uuid: str):
    info = FS.read_file_info(uuid=uuid)
    
    if info is None:
        raise HTTPException(status_code=404)

    response.headers["Tus-Resumable"] = tus_version
    response.headers["Upload-Length"] = str(info.upload_length)
    response.headers["Upload-Offset"] = str(info.offset)
    response.headers["Cache-Control"] = "no-store"

    if info.is_deferred:
        response.headers["Upload-Defer-Length"] = str(1)

    # Encode str to base64 
    if info.upload_metadata:
        metadata_base64 = ""
        for key, value in info.upload_metadata.items():
            metadata_base64 += f"{key} {base64.b64encode(bytes(value, 'utf-8'))},"
        response.headers["Upload-Metadata"] = metadata_base64.strip(",")

    response.status_code = 200
    return response


@router.patch("/files/{uuid}")
async def upload_file(request: Request, response: Response, uuid: str):
    tus_resumable = request.headers["Tus-Resumable"]
    content_length = int(request.headers["Content-Length"])
    content_type = request.headers["Content-Type"]
    upload_offset = int(request.headers["Upload-Offset"])

    assert tus_resumable == tus_version
    assert content_type == "application/offset+octet-stream"

    # PATCH request against a non-existent resource
    if not FS.is_existed(uuid):
        response.status_code = 404
        response.headers["Tus-Resumable"] = tus_version
        return

    info = FS.read_file_info(uuid)

    if info.defer_length:
        if request.headers["Upload-Length"]:
            response.status_code = 412
            response.headers["Tus-Resumable"] = tus_version
            return
        else:
            upload_length = int(request.headers["Upload-Length"])

        info.upload_length = upload_length
        
        FS.write_file_info(info)
    
    lock = FS.new_lock(uuid)
    
    with lock:
        # The Upload-Offset header's value MUST be equal to the current offset of the resource.
        if upload_offset != info.offset:
            response.status_code = 409
            response.headers["Tus-Resumable"] = tus_version
            return

        # Saving
        info = await _save_request_stream(request, uuid)

    # TODO: move above to `save_request_stream`
    if not info:
        response.status_code = 412
        response.headers["Tus-Resumable"] = tus_version
        return

    if upload_offset + content_length != info.offset:
        print(f"disconnect with client")
        response.status_code = 460
        response.headers["Tus-Resumable"] = tus_version
        return

    date_expiry = datetime.now() + timedelta(days=1)
    info.expires = str(date_expiry.isoformat())

    FS.write_file_info(info)

    # Upload file complete
    if info.upload_length == info.offset:
        # TODO: callbacks should be here
        pass

    response.headers["Location"] = f"{location}/{uuid}"
    response.headers["Tus-Resumable"] = tus_version
    response.headers["Upload-Offset"] = str(info.offset)
    response.headers["Upload-Expires"] = str(info.expires)
    response.status_code = 204
    return ""


"""
curl -v -X OPTIONS http://127.0.0.1:8000/files
"""


@router.options("/files", status_code=204)
async def read_tus_config(request: Request, response: Response):
    response.headers["Tus-Resumable"] = tus_version
    response.headers["Tus-Checksum-Algorithm"] = tus_checksum_algorithm
    response.headers["Tus-Version"] = tus_version
    response.headers["Tus-Max-Size"] = str(max_size)
    response.headers["Tus-Extension"] = tus_extension

    return ""


@router.delete("/files/{uuid}")
async def delete_file(request: Request):
    pass


async def _save_request_stream(
    request: Request, uuid: str, post_request: bool = False
) -> FileInfo | None:
    info = FS.read_file_info(uuid)

    f = open(f"{files_dir}/{uuid}", "ab")
    try:
        async for chunk in request.stream():
            chunk_size = len(chunk)
            f.write(chunk)
            info.offset += chunk_size
            info.upload_chunk_size = chunk_size
            info.upload_part += 1
    except ClientDisconnect as e:
        print(f"Client disconnected: {e}")
    finally:
        FS.write_file_info(info)
        f.close()

    return info