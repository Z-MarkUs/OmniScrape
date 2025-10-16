from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl
from typing import Literal
from datetime import datetime
import asyncio

from src.core.pipeline import extract


router = APIRouter(tags=["extraction"])


class ExtractRequest(BaseModel):
    url: HttpUrl
    kind: Literal["article", "product"]
    llmMode: Literal["none", "llm", "auto"] = "auto"


@router.post("/extract")
async def do_extract(req: ExtractRequest, request: Request):
    try:
        if await request.is_disconnected():
            return {"error": "Client disconnected"}

        if req.llmMode == "none":
            try:
                result = await extract(str(req.url), req.kind, "none")
                # ensure execution unit exists
                result.setdefault("_execution_time_unit", "ms")
                return {
                    "success": True,
                    "url": str(req.url),
                    "kind": req.kind,
                    "mode": req.llmMode,
                    "data": {**result, "extracted_at": datetime.now().isoformat()},
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"SD extraction failed: {str(e)}",
                    "url": str(req.url),
                    "kind": req.kind,
                    "mode": req.llmMode,
                }

        if req.llmMode in ["llm", "auto"]:
            try:
                result = await extract(str(req.url), req.kind, req.llmMode)
                # ensure execution unit exists
                result.setdefault("_execution_time_unit", "ms")
                return {
                    "success": True,
                    "url": str(req.url),
                    "kind": req.kind,
                    "mode": req.llmMode,
                    "data": {**result, "extracted_at": datetime.now().isoformat()},
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Extraction failed: {str(e)}",
                    "url": str(req.url),
                    "kind": req.kind,
                    "mode": req.llmMode,
                }

        return {
            "success": False,
            "error": "Unsupported mode",
            "mode": req.llmMode,
        }
    except asyncio.CancelledError:
        return {"error": "Extraction cancelled", "cancelled": True}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "trace": tb[-4000:]})


@router.post("/extract-stream")
async def do_extract_stream(req: ExtractRequest, request: Request):
    async def generate_progress():
        try:
            if await request.is_disconnected():
                yield f"data: {{\"type\": \"error\", \"message\": \"Client disconnected\"}}\n\n"
                return
            yield f"data: {{\"type\": \"progress\", \"step\": \"Starting extraction\"}}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {{\"type\": \"progress\", \"step\": \"Fetching page content\"}}\n\n"
            await asyncio.sleep(0.1)

            if req.llmMode == "none":
                yield f"data: {{\"type\": \"progress\", \"step\": \"Using Structured Data extraction\"}}\n\n"
                await asyncio.sleep(0.1)
                try:
                    result = await extract(str(req.url), req.kind, "none")
                    yield f"data: {{\"type\": \"progress\", \"step\": \"Processing structured data\"}}\n\n"
                    await asyncio.sleep(0.1)
                    from json import dumps
                    result.setdefault("_execution_time_unit", "ms")
                    payload = {"type":"complete","data":{**result, "extracted_at": datetime.now().isoformat()}}
                    yield f"data: {dumps(payload, default=str)}\n\n"
                except Exception as e:
                    from json import dumps
                    yield f"data: {dumps({'type':'error','message':f'SD extraction failed: {str(e)}'})}\n\n"
            elif req.llmMode in ("llm","auto"):
                yield f"data: {{\"type\": \"progress\", \"step\": \"Initializing AI model\"}}\n\n"
                await asyncio.sleep(0.1)
                try:
                    result = await extract(str(req.url), req.kind, req.llmMode)
                    yield f"data: {{\"type\": \"progress\", \"step\": \"Processing AI response\"}}\n\n"
                    await asyncio.sleep(0.1)
                    from json import dumps
                    result.setdefault("_execution_time_unit", "ms")
                    payload = {"type":"complete","data":{**result, "extracted_at": datetime.now().isoformat()}}
                    yield f"data: {dumps(payload, default=str)}\n\n"
                except Exception as e:
                    from json import dumps
                    yield f"data: {dumps({'type':'error','message':f'Extraction failed: {str(e)}'})}\n\n"
        except asyncio.CancelledError:
            yield "data: {\"type\": \"error\", \"message\": \"Extraction cancelled\"}\n\n"
        except Exception as e:
            from json import dumps
            yield f"data: {dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


