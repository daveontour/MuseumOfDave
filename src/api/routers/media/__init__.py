from fastapi import APIRouter
from .facebook_albums import router as facebook_albums_router
from .filesystem import router as filesystem_router
from .thumbnails import router as thumbnails_router
from .reference import router as reference_router
from .image_export import router as image_export_router
from .facebook_posts import router as facebook_posts_router
from .facebook_all import router as facebook_all_router
from .facebook_places import router as facebook_places_router
from .images import router as images_router

router = APIRouter()
router.include_router(facebook_albums_router)
router.include_router(filesystem_router)
router.include_router(thumbnails_router)
router.include_router(reference_router)
router.include_router(image_export_router)
router.include_router(facebook_posts_router)
router.include_router(facebook_all_router)
router.include_router(facebook_places_router)
router.include_router(images_router)
