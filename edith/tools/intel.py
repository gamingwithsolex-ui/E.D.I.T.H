import urllib.request
import urllib.parse
import json
import datetime
import re
import concurrent.futures
from edith.tools.search import _ddg_news

STREAM_HANDLES = {
    "sky": ("@SkyNews", "YDvsBbKfLPA"),
    "abc": ("@ABCNews", "iipR5yUp36o"),
    "bloomberg": ("@markets", "iEpJwprxDdk"),
    "kerala": ("@24OnLive", "1wECsnGZcfc")
}

_stream_cache = {}
_cache_duration = datetime.timedelta(hours=1)

def resolve_youtube_live_id(handle, fallback):
    url = f"https://www.youtube.com/{handle}/live"
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            content = response.read().decode('utf-8', errors='ignore')
            match_id = re.search(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', content)
            if match_id:
                return match_id.group(1)
            match_watch = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', content)
            if match_watch:
                return match_watch.group(1)
    except Exception as e:
        print(f"[INTEL] Live resolution error for {handle}: {e}")
    return fallback

def get_resolved_streams():
    now = datetime.datetime.now()
    resolved = {}
    
    # Check if cache is still valid
    cache_valid = True
    for key in STREAM_HANDLES:
        if key not in _stream_cache or _stream_cache[key][1] < now:
            cache_valid = False
            break
            
    if cache_valid:
        for key in STREAM_HANDLES:
            resolved[key] = _stream_cache[key][0]
        return resolved

    # Not valid, resolve in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(STREAM_HANDLES)) as executor:
        futures = {}
        for key, (handle, fallback) in STREAM_HANDLES.items():
            futures[executor.submit(resolve_youtube_live_id, handle, fallback)] = key
            
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                vid = future.result()
            except Exception:
                vid = STREAM_HANDLES[key][1]
            resolved[key] = vid
            _stream_cache[key] = (vid, now + _cache_duration)
            
    return resolved


def fetch_nvda_stock():
    """
    Fetch NVDA stock data from Yahoo Finance.
    Returns a dict with stock info and history or a graceful fallback.
    """
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/NVDA?range=1mo&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            res = data["chart"]["result"][0]
            meta = res["meta"]
            timestamps = res.get("timestamp", [])
            closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            
            prices = []
            dates = []
            for t, c in zip(timestamps, closes):
                if c is not None:
                    prices.append(round(c, 2))
                    dates.append(datetime.datetime.fromtimestamp(t).strftime('%b %d'))
            
            current_price = meta.get("regularMarketPrice")
            prev_close = meta.get("chartPreviousClose")
            
            if not current_price and prices:
                current_price = prices[-1]
            if not prev_close and len(prices) > 1:
                prev_close = prices[-2]
                
            change = current_price - prev_close if current_price and prev_close else 0
            change_pct = (change / prev_close) * 100 if prev_close else 0
            
            return {
                "symbol": "NVDA",
                "company": "NVIDIA Corporation",
                "currentPrice": round(current_price, 2) if current_price else 0.0,
                "change": round(change, 2),
                "changePercent": round(change_pct, 2),
                "history": {
                    "dates": dates,
                    "prices": prices
                }
            }
    except Exception as e:
        print(f"[STOCK ERROR] Failed to fetch NVDA stock: {e}")
        # Return fallback mock data if offline/blocked
        today = datetime.datetime.now()
        dates = [(today - datetime.timedelta(days=i)).strftime('%b %d') for i in range(15, 0, -1)]
        prices = [120.0 + (i * 1.5) for i in range(15)]
        return {
            "symbol": "NVDA",
            "company": "NVIDIA Corporation (Fallback Data)",
            "currentPrice": 142.50,
            "change": 2.15,
            "changePercent": 1.53,
            "history": {
                "dates": dates,
                "prices": prices
            }
        }

def fetch_f1_standings():
    """
    Fetch current F1 driver standings from the Jolpica-F1 API (Ergast successor).
    """
    try:
        url = "https://api.jolpi.ca/ergast/f1/current/driverStandings.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            lists = data['MRData']['StandingsTable']['StandingsLists']
            if not lists:
                return []
            standings = []
            for item in lists[0]['DriverStandings'][:10]:  # Top 10 drivers
                driver = item['Driver']
                constructor = item['Constructors'][0] if item.get('Constructors') else {"name": "Unknown"}
                standings.append({
                    "position": int(item['position']),
                    "points": float(item['points']),
                    "wins": int(item['wins']),
                    "driverName": f"{driver.get('givenName')} {driver.get('familyName')}",
                    "driverCode": driver.get('code', driver.get('familyName')[:3].upper()),
                    "constructor": constructor.get('name')
                })
            return standings
    except Exception as e:
        print(f"[F1 ERROR] Failed to fetch F1 standings: {e}")
        # Return fallback mock F1 data if offline/blocked
        return [
            {"position": 1, "points": 110, "wins": 3, "driverName": "Max Verstappen", "driverCode": "VER", "constructor": "Red Bull Racing"},
            {"position": 2, "points": 88, "wins": 1, "driverName": "Charles Leclerc", "driverCode": "LEC", "constructor": "Ferrari"},
            {"position": 3, "points": 75, "wins": 0, "driverName": "Sergio Perez", "driverCode": "PER", "constructor": "Red Bull Racing"},
            {"position": 4, "points": 62, "wins": 0, "driverName": "Lando Norris", "driverCode": "NOR", "constructor": "McLaren"},
            {"position": 5, "points": 58, "wins": 0, "driverName": "Carlos Sainz", "driverCode": "SAI", "constructor": "Ferrari"},
            {"position": 6, "points": 45, "wins": 0, "driverName": "Oscar Piastri", "driverCode": "PIA", "constructor": "McLaren"},
            {"position": 7, "points": 38, "wins": 0, "driverName": "George Russell", "driverCode": "RUS", "constructor": "Mercedes"},
            {"position": 8, "points": 32, "wins": 0, "driverName": "Lewis Hamilton", "driverCode": "HAM", "constructor": "Mercedes"},
            {"position": 9, "points": 18, "wins": 0, "driverName": "Fernando Alonso", "driverCode": "ALO", "constructor": "Aston Martin"},
            {"position": 10, "points": 12, "wins": 0, "driverName": "Yuki Tsunoda", "driverCode": "TSU", "constructor": "RB"}
        ]

def fetch_f1_constructor_standings():
    """
    Fetch F1 constructor standings.
    """
    try:
        url = "https://api.jolpi.ca/ergast/f1/current/constructorStandings.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            lists = data['MRData']['StandingsTable']['StandingsLists']
            if not lists:
                return []
            standings = []
            for item in lists[0]['ConstructorStandings'][:10]:
                constructor = item['Constructor']
                standings.append({
                    "position": int(item['position']),
                    "points": float(item['points']),
                    "wins": int(item['wins']),
                    "constructorName": constructor.get('name')
                })
            return standings
    except Exception as e:
        print(f"[F1 ERROR] Failed to fetch F1 constructor standings: {e}")
        return [
            {"position": 1, "points": 185, "wins": 3, "constructorName": "Red Bull Racing"},
            {"position": 2, "points": 146, "wins": 1, "constructorName": "Ferrari"},
            {"position": 3, "points": 107, "wins": 0, "constructorName": "McLaren"},
            {"position": 4, "points": 70, "wins": 0, "constructorName": "Mercedes"},
            {"position": 5, "points": 30, "wins": 0, "constructorName": "Aston Martin"}
        ]

def fetch_f1_last_race():
    """
    Fetch last race results.
    """
    try:
        url = "https://api.jolpi.ca/ergast/f1/current/last/results.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            races = data['MRData']['RaceTable']['Races']
            if not races:
                return {}
            race = races[0]
            results = []
            for item in race.get('Results', [])[:10]:
                driver = item['Driver']
                results.append({
                    "position": int(item['position']),
                    "points": float(item.get('points', 0)),
                    "driverName": f"{driver.get('givenName')} {driver.get('familyName')}",
                    "driverCode": driver.get('code', driver.get('familyName')[:3].upper()),
                    "constructor": item['Constructor'].get('name')
                })
            return {
                "raceName": race.get('raceName'),
                "date": race.get('date'),
                "results": results
            }
    except Exception as e:
        print(f"[F1 ERROR] Failed to fetch last race results: {e}")
        return {
            "raceName": "Miami Grand Prix",
            "date": "2026-05-03",
            "results": [
                {"position": 1, "points": 25.0, "driverName": "Lando Norris", "driverCode": "NOR", "constructor": "McLaren"},
                {"position": 2, "points": 18.0, "driverName": "Max Verstappen", "driverCode": "VER", "constructor": "Red Bull Racing"},
                {"position": 3, "points": 15.0, "driverName": "Charles Leclerc", "driverCode": "LEC", "constructor": "Ferrari"},
                {"position": 4, "points": 12.0, "driverName": "Carlos Sainz", "driverCode": "SAI", "constructor": "Ferrari"},
                {"position": 5, "points": 10.0, "driverName": "Sergio Perez", "driverCode": "PER", "constructor": "Red Bull Racing"}
            ]
        }

def fetch_f1_next_race():
    """
    Fetch next race status details.
    """
    try:
        url = "https://api.jolpi.ca/ergast/f1/current/next.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            races = data['MRData']['RaceTable']['Races']
            if not races:
                return {}
            race = races[0]
            circuit = race.get('Circuit', {})
            loc = circuit.get('Location', {})
            return {
                "raceName": race.get('raceName'),
                "date": race.get('date'),
                "time": race.get('time'),
                "circuitName": circuit.get('circuitName'),
                "locality": loc.get('locality'),
                "country": loc.get('country')
            }
    except Exception as e:
        print(f"[F1 ERROR] Failed to fetch next race: {e}")
        return {
            "raceName": "Canadian Grand Prix",
            "date": "2026-05-24",
            "time": "20:00:00Z",
            "circuitName": "Circuit Gilles Villeneuve",
            "locality": "Montreal",
            "country": "Canada"
        }

def fetch_f1_intel():
    """
    Fetch all F1 details in parallel using ThreadPoolExecutor.
    """
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_drivers = executor.submit(fetch_f1_standings)
        future_constructors = executor.submit(fetch_f1_constructor_standings)
        future_last = executor.submit(fetch_f1_last_race)
        future_next = executor.submit(fetch_f1_next_race)
        
        results["drivers"] = future_drivers.result()
        results["constructors"] = future_constructors.result()
        results["last_race"] = future_last.result()
        results["next_race"] = future_next.result()
    return results

def get_briefing_data():
    """
    Compile all information for the global briefing page.
    """
    stock = fetch_nvda_stock()
    f1_data = fetch_f1_intel()
    news_streams = get_resolved_streams()
    
    # Fetch general world news
    news_items = _ddg_news("world news", max_results=5)
    news_formatted = []
    if news_items:
        for n in news_items:
            news_formatted.append({
                "title": n.get("title", ""),
                "body": n.get("body", ""),
                "date": n.get("date", "")[:10] if n.get("date") else ""
            })
    else:
        news_formatted = [
            {"title": "Global Markets Rally Amid Tech Sector Growth", "body": "International indices showed strong gains today, driven by semiconductor and generative AI demand.", "date": ""},
            {"title": "Formula 1 Championship Intensifies", "body": "Teams are gearing up for the next grand prix as constructors prepare performance upgrades.", "date": ""},
            {"title": "Space Agency Announces New Lunar Partnership", "body": "International coalition signs agreement for deep-space communication networks.", "date": ""}
        ]
        
    return {
        "stock": stock,
        "f1": f1_data,
        "news": news_formatted,
        "news_streams": news_streams
    }

def generate_llm_context(data):
    """
    Build a text summary that will be passed as context to the LLM (Main Brain).
    """
    stock = data["stock"]
    f1 = data["f1"]
    news = data["news"]
    
    lines = []
    lines.append("=== GLOBAL BRIEFING INTEL ===")
    lines.append(f"NVIDIA Stock (NVDA): ${stock['currentPrice']} (Change: {stock['change']} ({stock['changePercent']}%))")
    
    if isinstance(f1, dict):
        drivers = f1.get("drivers", [])
        constructors = f1.get("constructors", [])
        last_race = f1.get("last_race", {})
        next_race = f1.get("next_race", {})
        
        lines.append("\nTop 5 F1 Driver Standings:")
        for item in drivers[:5]:
            lines.append(f"  {item['position']}. {item['driverName']} ({item['constructor']}) - {item['points']} pts, {item['wins']} wins")
            
        lines.append("\nTop 3 F1 Constructor Standings:")
        for item in constructors[:3]:
            lines.append(f"  {item['position']}. {item['constructorName']} - {item['points']} pts, {item['wins']} wins")
            
        if last_race:
            lines.append(f"\nLast Race Results ({last_race.get('raceName')}):")
            for item in last_race.get('results', [])[:3]:
                lines.append(f"  {item['position']}. {item['driverName']} ({item['constructor']})")
                
        if next_race:
            lines.append(f"\nNext Race Status: {next_race.get('raceName')} on {next_race.get('date')} at {next_race.get('circuitName')}")
    else:
        lines.append("\nTop 5 F1 Driver Standings:")
        for item in f1[:5]:
            lines.append(f"  {item['position']}. {item['driverName']} ({item['constructor']}) - {item['points']} pts, {item['wins']} wins")
        
    lines.append("\nTop World News Headlines:")
    for n in news[:3]:
        lines.append(f"  - {n['title']}: {n['body'][:150]}...")
        
    return "\n".join(lines)
