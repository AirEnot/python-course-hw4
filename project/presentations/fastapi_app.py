from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, HttpUrl
from services.link_service import LinkService
from urllib.parse import urlparse
import requests
import time
from typing import Callable, Awaitable
from fastapi import Request, Response
from loguru import logger
from fastapi.responses import JSONResponse
from datetime import datetime
import json


def create_app() -> FastAPI:
    app = FastAPI()
    short_link_service = LinkService()

    class PutLink(BaseModel):
        link: str

    def _service_link_to_real(short_link: str) -> str:
        return f"http://localhost:8000/{short_link}"

    def is_valid_url(link: PutLink) -> bool:
        parsed = urlparse(link.link)
        if not all([parsed.scheme, parsed.netloc]):
            return False
        

    def add_http(processed_link: PutLink) -> PutLink:
        parsed = urlparse(processed_link.link)
        if parsed.scheme:
            return processed_link
        
        return PutLink(link = f"https://{processed_link.link}")

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "level": "ERROR",
            "type": "UNHANDLED_EXCEPTION",
            "request": {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
            }
        }
        
        logger.error("Критическая ошибка:\n{}", json.dumps(error_data, indent=2))
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "timestamp": error_data["timestamp"],
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        )


    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next) -> Response:
        t0 = time.time()
        
        response = await call_next(request)

        elapsed_ms = round((time.time() - t0) * 1000, 2)
        response.headers["X-Latency"] = str(elapsed_ms)
        logger.debug("{} {} done in {}ms", request.method, request.url, elapsed_ms)
        
        return response

    @app.post("/link")
    def create_link(put_link_request: PutLink) -> PutLink:
        if put_link_request.link == 'google.com': a = 1 / 0
        put_link_request = add_http(put_link_request)
        
        if is_valid_url(put_link_request) == False:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link is not valid")
        
        short_link = short_link_service.create_link(put_link_request.link)
        return PutLink(link=_service_link_to_real(short_link))

    @app.get("/{link}")
    def get_link(link: str) -> Response:
        real_link = short_link_service.get_real_link(link)
        if real_link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found:(")

        return Response(status_code=status.HTTP_301_MOVED_PERMANENTLY, headers={"Location": real_link})

    return app
