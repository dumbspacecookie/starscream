from fastapi import APIRouter

from starscream.api.routes.admin import router as admin_router
from starscream.api.routes.contrib import router as contrib_router
from starscream.api.routes.contributors import router as contributors_router
from starscream.api.routes.federation import router as federation_router
from starscream.api.routes.governance import router as governance_router
from starscream.api.routes.recordings import router as recordings_router
from starscream.api.routes.reviews import router as reviews_router
from starscream.api.routes.search import router as search_router
from starscream.api.routes.sensor import router as sensor_router
from starscream.api.routes.sources import router as sources_router
from starscream.api.routes.stats import router as stats_router
from starscream.api.routes.stream import router as stream_router
from starscream.api.routes.taxonomy import router as taxonomy_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(recordings_router)
api_router.include_router(reviews_router)
api_router.include_router(contrib_router)
api_router.include_router(contributors_router)
api_router.include_router(admin_router)
api_router.include_router(federation_router)
api_router.include_router(governance_router)
api_router.include_router(sensor_router)
api_router.include_router(taxonomy_router)
api_router.include_router(sources_router)
api_router.include_router(stats_router)
api_router.include_router(search_router)
api_router.include_router(stream_router)
