# FastAPI Server for Tus Protocol

A file upload server of the tus resumable upload protocol is implemented on FastAPI framework.  

## Getting started

Import `TusRouter` to your application,

```py title=main.py
from fastapi import FastAPI
from fastapi_tusd import TusRouter

app = FastAPI()

app.include_router(TusRouter(store_dir="./files", prefix="/files"))
```

Then the tus upload endpoints will be served at `http://127.0.0.1:8000/files`, more information is available at `http://127.0.0.1:8000/docs`

### Example with Tus Client

A simple example with web client using `uppy` to support for `Tus` protocol, under the `example/` folder

```sh
uvicorn app_tusd:app --reload
```

Then visit `https://127.0.0.1:8000/upload.thml`

## References

[GitHub - tus/tus-resumable-upload-protocol: Open Protocol for Resumable File Uploads](https://github.com/tus/tus-resumable-upload-protocol)