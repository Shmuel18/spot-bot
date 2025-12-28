from pydantic import BaseModel, Field, field_validator
from typing import List


class BotConfig(BaseModel):
    timeframe: str = Field(..., description="Timeframe for candles, e.g., '1h', '15m'")
    sma_length: int = Field(..., gt=0, description="Number of candles for SMA calculation")
    dip_threshold: float = Field(..., ge=-100, le=0, description="Dip threshold percentage for entry")
    position_size_percent: float = Field(..., gt=0, le=100, description="Position size as % of equity")
    tp_percent: float = Field(..., gt=0, description="Take profit percentage")
    dca_scales: List[float] = Field(..., min_length=1, description="DCA scales as multipliers")
    dca_trigger: float = Field(..., gt=0, description="DCA trigger drop percentage")
    max_positions: int = Field(..., gt=0, description="Maximum open positions")
    min_24h_volume: float = Field(..., gt=0, description="Minimum 24h volume in USDT")
    daily_loss_limit: float = Field(..., ge=0, le=100, description="Daily loss limit percentage")
    sleep_interval: int = Field(..., gt=0, description="Sleep interval between loops in seconds")
    blacklist: List[str] = Field(default_factory=list, description="Blacklisted symbols")
    dry_run: bool = Field(default=True, description="Dry run mode")

    @field_validator('timeframe')
    @classmethod
    def validate_timeframe(cls, v):
        if not v or v[-1] not in ['m', 'h', 'd']:
            raise ValueError('Timeframe must end with m, h, or d')
        try:
            int(v[:-1])
        except ValueError:
            raise ValueError('Timeframe value must be numeric')
        return v

    @field_validator('dca_scales')
    @classmethod
    def validate_dca_scales(cls, v):
        if not all(isinstance(x, (int, float)) and x > 0 for x in v):
            raise ValueError('DCA scales must be positive numbers')
        return v