import json
import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Item
from app.redis_client import get_redis
from app.schemas import ItemCreate, ItemRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/items", tags=["items"])
settings = get_settings()

_CACHE_KEY = "items:{id}"


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
) -> Item:
    item = Item(name=payload.name, description=payload.description)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    logger.info("item created", extra={"item_id": item.id})
    return item


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis),
) -> Item:
    key = _CACHE_KEY.format(id=item_id)

    # Cache-aside read. A Redis outage must not break the endpoint.
    try:
        cached = await cache.get(key)
        if cached:
            logger.info("cache hit", extra={"item_id": item_id})
            return ItemRead.model_validate(json.loads(cached))
    except Exception:
        logger.warning("redis read failed; falling back to db", exc_info=True)

    item = await db.get(Item, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="item not found"
        )

    try:
        await cache.set(
            key,
            ItemRead.model_validate(item).model_dump_json(),
            ex=settings.cache_ttl_seconds,
        )
    except Exception:
        logger.warning("redis write failed", exc_info=True)

    return item


@router.get("", response_model=list[ItemRead])
async def list_items(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[Item]:
    limit = min(max(limit, 1), 100)
    result = await db.execute(
        select(Item).order_by(Item.id.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis),
) -> None:
    item = await db.get(Item, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="item not found"
        )
    await db.delete(item)
    await db.commit()

    try:
        await cache.delete(_CACHE_KEY.format(id=item_id))
    except Exception:
        logger.warning("redis delete failed", exc_info=True)

    logger.info("item deleted", extra={"item_id": item_id})
