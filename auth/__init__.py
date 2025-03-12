from auth.google import google_router
from auth.vipps import vipps_router
from auth.local import local_router

__all__ = ["google_router", "vipps_router", "local_router"]