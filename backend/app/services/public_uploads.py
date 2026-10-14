from pathlib import PurePosixPath

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class PublicUploads(StaticFiles):
    async def get_response(self, path, scope):
        if any(part.startswith(".") for part in PurePosixPath(path).parts):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)
