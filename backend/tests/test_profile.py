from .conftest import player


async def test_own_and_other_profile(client):
    h1 = await player(client, 400)
    await player(client, 401)
    await client.post("/api/tap", json={"taps": 4}, headers=h1)
    mine = (await client.get("/api/profile", headers=h1)).json()
    assert mine["id"] == 400 and mine["hero"]["id"] == "pudge" and "coins" in mine
    assert mine["month"]["points"] == 4 and mine["look"]["body"].endswith("pudge.glb")
    assert len(mine["heroes"]) == 6 and mine["heroes"][0]["owned"]
    other = (await client.get("/api/profile/400", headers=await player(client, 402))).json()
    assert other["name"] == "dev400" and "coins" not in other and "souls" not in other
    assert (await client.get("/api/profile/999999", headers=h1)).status_code == 404
    top = (await client.get("/api/top/month", headers=h1)).json()
    assert top["top"][0]["id"] == 400
