from fastapi import FastAPI
from pydantic import BaseModel
from .ml_optimizer import MLTradingOptimizer

app = FastAPI()

# Initialize the ML optimizer
optimizer = MLTradingOptimizer()

class PredictionRequest(BaseModel):
    symbol: str
    bid_ask_imbalance: float
    spread_percent: float
    mid_price: float
    bid_volume: float
    ask_volume: float
    order_book_depth: int
    large_bid_wall: bool
    large_ask_wall: bool
    wall_size: float
    volume_weighted_price: float
    price_momentum: float
    volatility: float
    timestamp: int

@app.post("/predict")
async def predict(request: PredictionRequest):
    features = {
        "symbol": request.symbol,
        "bid_ask_imbalance": request.bid_ask_imbalance,
        "spread_percent": request.spread_percent,
        "mid_price": request.mid_price,
        "bid_volume": request.bid_volume,
        "ask_volume": request.ask_volume,
        "order_book_depth": request.order_book_depth,
        "large_bid_wall": request.large_bid_wall,
        "large_ask_wall": request.large_ask_wall,
        "wall_size": request.wall_size,
        "volume_weighted_price": request.volume_weighted_price,
        "price_momentum": request.price_momentum,
        "volatility": request.volatility,
        "timestamp": request.timestamp
    }
    prediction = optimizer.predict_trading_signal(features)
    return prediction

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
