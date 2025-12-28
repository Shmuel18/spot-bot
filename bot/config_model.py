from pydantic import BaseModel, Field, field_validator
from typing import List
from decimal import Decimal

class BotConfig(BaseModel):
    timeframe: str = Field(..., description="Timeframe for candles, e.g., '1h', '15m'")
    sma_length: int = Field(..., gt=0, description="Number of candles for SMA calculation")
    dip_threshold: Decimal = Field(..., description="Dip threshold percentage for entry")
    position_size_percent: Decimal = Field(..., gt=0, le=100)
    tp_percent: Decimal = Field(..., gt=0)
    dca_scales: List[Decimal] = Field(..., min_length=1)
    dca_trigger: Decimal = Field(..., gt=0)
    max_positions: int = Field(..., gt=0)
    min_24h_volume: Decimal = Field(..., gt=0)
    daily_loss_limit: Decimal = Field(..., ge=0, le=100)
    sleep_interval: int = Field(..., gt=0)
    blacklist: List[str] = Field(default_factory=list)
    dry_run: bool = Field(default=True)

    @field_validator('timeframe')
    @classmethod
    def validate_timeframe(cls, v):
        if not v or v[-1] not in ['m', 'h', 'd']:
            raise ValueError('Timeframe must end with m, h, or d')
        return v