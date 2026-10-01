from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import analysis, trading, news, dashboard, backtest
from api.core.config import settings

app = FastAPI(
    title="AI Trading & Scalping System API",
    description="API for multi-layer market-analysis methodology and scalping research platform.",
    version="1.0.0"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Market Analysis"])
app.include_router(trading.router, prefix="/api/v1/trading", tags=["Paper Trading & Setup"])
app.include_router(news.router, prefix="/api/v1/news", tags=["News Engine"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard Metrics"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtesting"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "AI Trading System API is running"}
