async def _create(client, name="widget", description="a thing"):
    resp = await client.post(
        "/items", json={"name": name, "description": description}
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_item(client):
    body = await _create(client)
    assert body["id"] > 0
    assert body["name"] == "widget"
    assert body["description"] == "a thing"
    assert "created_at" in body


async def test_create_item_validation_error(client):
    # Empty name violates min_length=1.
    resp = await client.post("/items", json={"name": ""})
    assert resp.status_code == 422


async def test_get_item_populates_cache(client, fake_redis):
    created = await _create(client)
    item_id = created["id"]

    assert await fake_redis.get(f"items:{item_id}") is None

    resp = await client.get(f"/items/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id

    # Read-through cache should now hold the serialized item.
    cached = await fake_redis.get(f"items:{item_id}")
    assert cached is not None


async def test_get_item_served_from_cache(client, fake_redis):
    created = await _create(client)
    item_id = created["id"]

    # Prime the cache, then a second read returns identical data.
    first = (await client.get(f"/items/{item_id}")).json()
    second = (await client.get(f"/items/{item_id}")).json()
    assert first == second


async def test_get_missing_item_returns_404(client):
    resp = await client.get("/items/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "item not found"


async def test_list_items_orders_desc(client):
    a = await _create(client, name="first")
    b = await _create(client, name="second")

    resp = await client.get("/items")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert ids[:2] == [b["id"], a["id"]]


async def test_delete_item_invalidates_cache(client, fake_redis):
    created = await _create(client)
    item_id = created["id"]

    await client.get(f"/items/{item_id}")  # populate cache
    assert await fake_redis.get(f"items:{item_id}") is not None

    resp = await client.delete(f"/items/{item_id}")
    assert resp.status_code == 204

    assert await fake_redis.get(f"items:{item_id}") is None
    assert (await client.get(f"/items/{item_id}")).status_code == 404
