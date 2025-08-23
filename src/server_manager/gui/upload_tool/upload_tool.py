import asyncio
import os
import threading
from importlib.resources import files
from signal import SIGTERM

from fastapi.staticfiles import StaticFiles
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from server_manager.common.singleton import SingletonMeta


class _UploadServer(metaclass=SingletonMeta):
    def __init__(self, allowed_ip: str, server_dest_path: str, expire_time_sec: int = 60):
        self.app = FastAPI()
        self.allowed_ip = allowed_ip
        self.server_dest_path = server_dest_path
        self.expire_time_sec = expire_time_sec
        # set timer, close server after expire_time_sec
        if self.expire_time_sec > 0:
            self.timer = threading.Timer(self.expire_time_sec, self.shutdown_server)
            self.timer.start()
        self.server = None  # Will hold the Uvicorn server instance
        self.app.mount(
            "/images", StaticFiles(directory=str(files("server_manager") / "gui/upload_tool/images/")), name="images/"
        )

        # redirect no path
        @self.app.get("/")
        async def redirect_to_upload():
            return HTMLResponse(status_code=302, headers={"Location": "/upload/"})

        @self.app.get("/favicon.ico", response_class=HTMLResponse)
        async def get_favicon():
            return (files("server_manager") / "gui/upload_tool/favicon.ico").read_bytes()

        @self.app.get("/upload/", response_class=HTMLResponse)
        async def get_upload_file():
            return (files("server_manager") / "gui/upload_tool/index.html").read_text(encoding="utf-8")

        @self.app.post("/upload/")
        async def create_upload_file(request: Request):
            if request.client is None:
                return """<h1>Error: No client information available</h1>"""
            if request.client.host != self.allowed_ip:
                await request.close()
                return {"error": "Unauthorized client"}, 403
            if request is None:
                return {"error": "No file provided"}, 400
            # python-multipart
            form = await request.form()
            file = form.get("file")
            if not file or isinstance(file, str):
                return {"error": "No file provided"}, 400
            with open(self.server_dest_path, "wb") as f:
                f.write(await file.read())
            return {"message": "Upload complete"}

    def __del__(self):
        self.shutdown_server()

    def shutdown_server(self):
        if self.timer:
            self.timer.cancel()
        os.kill(os.getpid(), SIGTERM)


async def start_server(client_ip: str, dest_path: str) -> threading.Thread:
    app = _UploadServer(allowed_ip=client_ip, server_dest_path=dest_path, expire_time_sec=-1)
    uvicorn_thread = threading.Thread(
        target=uvicorn.run, args=(app.app,), kwargs={"host": "0.0.0.0", "port": 8000, "log_level": "trace"}
    )
    await asyncio.to_thread(uvicorn_thread.start)
    return uvicorn_thread


windows_client_ip = os.popen("ip route show | grep -i default | awk '{ print $3}'").read().strip()
print(f"Detected Windows client IP: {windows_client_ip}")
asyncio.run(start_server(windows_client_ip, "test.jpg"))
