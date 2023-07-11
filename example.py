from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Router


from starlette.responses import PlainTextResponse
import inspect

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def homepage(request):
    print(request.headers)
    c = request.headers.get("Connection") == 'keep-alive'
    print(c)
    return PlainTextResponse("Homepage")

async def about(request):
    return PlainTextResponse("About")


routes = [
    Route("/", endpoint=homepage),
    Route("/about", endpoint=about),
]

app = Router(routes=routes)