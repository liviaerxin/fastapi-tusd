# FastAPI Server for Tus Protocol

A file upload server of the tus resumable upload protocol is implemented on **FastAPI** framework.  

Thanks to [tusd](https://github.com/tus/tusd), it provides great ideas and a sensible design pattern to implement `Tus` protocol to support multiple backend storage implementations.

**Features**:

- [x] Basic operations to support Core Protocol such as **HEAD**, **POST**, **PATCH**, **DELETE**
  - [x] Creation With Upload
  - [ ] Checksum such as md5
  - [ ] Expiration
  - [ ] Concatenation
- [x] File storage
- [ ] S3 storage


## Getting started

Import `TusRouter` to your application,

```py title=main.py
from fastapi import FastAPI
from fastapi_tusd import TusRouter

app = FastAPI()

# `store_dir`: the folder to store uploaded files
#  `location`: the API endpoint to serve, like `http://127.0.0.1:8000/files` or relative path `files` (TODO: induced from `prefix` in default)
app.include_router(TusRouter(store_dir="./files", location="/files"), prefix="/files")
```

Then the tus upload endpoints will be served at `http://127.0.0.1:8000/files`, more information is available at `http://127.0.0.1:8000/docs`

### Examples

There is a simple example with a web file upload client supporting for `Tus` protocol, thanks to `Uppy`!

Enter the `example/` folder, and run(`pip install `uvicorn` if no `uvicorn`!)

```sh
uvicorn app_tusd:app --reload
```

Then visit `https://127.0.0.1:8000/upload.thml`

## References

[GitHub - tus/tus-resumable-upload-protocol: Open Protocol for Resumable File Uploads](https://github.com/tus/tus-resumable-upload-protocol)
