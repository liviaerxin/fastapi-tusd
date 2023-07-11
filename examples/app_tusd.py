from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi_tusd import TusRouter

app = FastAPI()

app.include_router(TusRouter(store_dir="./files"))

# fmt: off
html_content = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Uppy</title>
    <link href="https://releases.transloadit.com/uppy/v3.3.1/uppy.min.css" rel="stylesheet">
</head>
<body>
<div id="drag-drop-area"></div>

<script type="module">
    import {Uppy, Dashboard, Tus} from "https://releases.transloadit.com/uppy/v3.3.1/uppy.min.mjs"
    var uppy = new Uppy()
        .use(Dashboard, {
            inline: true,
            target: '#drag-drop-area'
        })
        .use(Tus, {endpoint: '/files'})

    uppy.on('complete', (result) => {
        console.log('Upload complete! We’ve uploaded these files:', result.successful)
    })
</script>
</body>
</html>
"""
# fmt: on

@app.get("/")
async def home():
    return {"message": "Hello World"}

@app.get("/upload.html")
async def read_uppy():
    return HTMLResponse(html_content)