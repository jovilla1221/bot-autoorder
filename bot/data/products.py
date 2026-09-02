PRODUCTS = [
    {
        "id": "netflix_trial_reg_th",
        "name": "Netflix Trial REG TH",
        "description": "Akun Netflix trial region Thailand\nDurasi: 30 hari\nJaminan: Private account",
        "price": 25000,
        "category": "streaming",
    },
    {
        "id": "spotify_premium_id",
        "name": "Spotify Premium ID",
        "description": "Spotify Premium individual 1 bulan\nRegion: Indonesia\nAuto-renew off",
        "price": 15000,
        "category": "music",
    },
    {
        "id": "youtube_premium",
        "name": "YouTube Premium",
        "description": "YouTube Premium 1 bulan\nNo ads, background play, YT Music",
        "price": 35000,
        "category": "streaming",
    },
]

def get_product(pid: str):
    for p in PRODUCTS:
        if p["id"] == pid:
            return p
    return None

def product_index(pid: str) -> int:
    for i, p in enumerate(PRODUCTS):
        if p["id"] == pid:
            return i
    return -1