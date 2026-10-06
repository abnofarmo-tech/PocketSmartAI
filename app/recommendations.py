from urllib.parse import quote_plus

from app.config import settings
from app.schemas import Recommendation

PLANNER_NAMES = {"home": "Home decor", "party": "Party planning", "jewelry": "Jewelry"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _details(payload: dict) -> str:
    return "; ".join(f"{key}: {value}" for key, value in payload.items() if value not in (None, "", []))


def demo_recommendation(planner: str, payload: dict) -> Recommendation:
    budget = float(payload["budget"])
    if planner == "home":
        labels = ["Lighting", "Soft furnishings", "Storage", "Wall decor"]
        suggestions = ["Energy-saving room lights", "Curtains and cushion covers", "Compact storage unit", "Framed wall art"]
        retailers = ["Amazon", "IKEA", "Flipkart", "IKEA"]
    elif planner == "party":
        labels = ["Food", "Decor", "Entertainment", "Contingency"]
        suggestions = ["Simple catering or snacks", "Reusable table and room decor", "Playlist or small activity setup", "Reserve for service fees"]
        retailers = ["Swiggy", "Amazon", "Amazon", "Amazon"]
    else:
        labels = ["Earrings", "Necklace", "Bangle or bracelet", "Hair accessory"]
        suggestions = ["Lightweight occasion earrings", "Simple matching necklace", "Minimal bracelet", "Small coordinating accessory"]
        retailers = ["Amazon", "Flipkart", "Amazon", "Flipkart"]
    weights = [0.38, 0.27, 0.20, 0.15]
    items = []
    for label, suggestion, retailer, weight in zip(labels, suggestions, retailers, weights):
        query = f"{suggestion} {payload.get('style', payload.get('event_type', payload.get('occasion', '')))}".strip()
        items.append({"title": suggestion, "category": label, "estimated_price": round(budget * weight, 2),
                      "rationale": f"A demo allocation for {label.lower()} within your stated budget.",
                      "retailer": retailer, "search_query": query})
    estimated_total = round(sum(item["estimated_price"] for item in items), 2)
    return Recommendation(title=f"{PLANNER_NAMES[planner]} starter plan",
        summary=f"A sample {PLANNER_NAMES[planner].lower()} plan based on your inputs ({_details(payload)}). Adjust the split to suit your priorities.",
        total_budget=budget, total_estimated=estimated_total, items=items,
        tips=["Keep a small reserve for delivery, taxes, or service fees.", "Compare current listings before buying."],
        caveats=["Demo estimates only; no live retailer inventory or prices were checked."], source="Demo estimate")


def _fit_budget(result: Recommendation, budget: float, planner: str) -> Recommendation:
    if not result.items:
        raise ValueError("The recommendation did not include any items.")
    prices = [max(0.0, float(item.estimated_price)) for item in result.items]
    total = sum(prices)
    if total > budget and total:
        prices = [price * budget / total for price in prices]
    items = []
    for item, price in zip(result.items, prices):
        data = item.model_dump()
        data["estimated_price"] = round(price, 2)
        data["search_query"] = data["search_query"] or data["title"]
        items.append(data)
    overflow = round(sum(item["estimated_price"] for item in items) - budget, 2)
    if overflow > 0:
        items[-1]["estimated_price"] = max(0.0, round(items[-1]["estimated_price"] - overflow, 2))
    exact_total = round(sum(item["estimated_price"] for item in items), 2)
    return Recommendation(title=result.title, summary=result.summary, total_budget=budget,
        total_estimated=exact_total, items=items,
        tips=result.tips[:6], caveats=(result.caveats + ["Prices are AI-generated estimates, not verified retailer prices."])[:6],
        source="AI estimate")


def generate_recommendation(planner: str, payload: dict, image_bytes: bytes | None = None,
                             image_mime: str | None = None) -> Recommendation:
    if not settings.gemini_api_key:
        return demo_recommendation(planner, payload)
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = f"""Create a practical {PLANNER_NAMES[planner]} plan using the user's stated inputs.
Budget is INR {payload['budget']}. Never exceed the budget. Use plausible cost estimates,
not claims about current listings. Return 3-8 useful items and specific short rationales.
Do not invent live inventory, discounts, product URLs, or vendor API results. Select retailers
only from Amazon, Flipkart, IKEA, Swiggy, Zomato, OYO. Make search_query concise.
Inputs: {_details(payload)}
The optional image is a style reference only; do not infer sensitive traits about people."""
        parts: list = [prompt]
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime or "image/jpeg"))
        response = client.models.generate_content(model=settings.gemini_model, contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Recommendation))
        result = Recommendation.model_validate_json(response.text or "")
        return _fit_budget(result, float(payload["budget"]), planner)
    except Exception as exc:
        # Don't silently present the demo plan as an AI result when the configured API fails.
        raise RuntimeError("Gemini could not generate a recommendation. Check your API key, model name, and network, then try again.") from exc


def retailer_search_url(retailer: str, query: str) -> str:
    q = quote_plus(query)
    urls = {
        "Amazon": f"https://www.amazon.in/s?k={q}",
        "Flipkart": f"https://www.flipkart.com/search?q={q}",
        "IKEA": f"https://www.ikea.com/in/en/search/?q={q}",
        "Swiggy": f"https://www.swiggy.com/search?query={q}",
        "Zomato": f"https://www.zomato.com/search?q={q}",
        "OYO": f"https://www.oyorooms.com/search?location={q}",
    }
    return urls.get(retailer, urls["Amazon"])
