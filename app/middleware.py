from collections import deque


async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response



class RequestSizeLimit:
    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        messages = deque()
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json")]})
                return await send({"type": "http.response.body",
                                   "body": b'{"detail":"Request is too large."}'})
            messages.append(message)
            if not message.get("more_body", False):
                break
        async def replay():
            if messages:
                return messages.popleft()
            return await receive()
        await self.app(scope, replay, send)
