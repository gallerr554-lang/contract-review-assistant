from fastapi import APIRouter

from app.api import auth, contract, model, review, rule, scene, user
from app.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(contract.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(review.router, prefix="/review", tags=["review"])
api_router.include_router(rule.router, prefix="/rules", tags=["rules"])
api_router.include_router(scene.router, prefix="/scenes", tags=["scenes"])
api_router.include_router(model.router, prefix="/models", tags=["models"])
api_router.include_router(user.router, prefix="/users", tags=["users"])
