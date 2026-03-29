"""Pydantic schemas for the Active Alpha API."""

from app.schemas.backtest import (
    BacktestConfigSchema,
    BacktestMetrics,
    BacktestResultSchema,
    EquityCurvePoint,
    MonthlyReturn,
    PrecomputedStrategySchema,
)
from app.schemas.benchmark import (
    BenchmarkHoldingRecord,
    BenchmarkHoldingsResponse,
    BenchmarkResponse,
)
from app.schemas.common import CursorPagination, ErrorResponse
from app.schemas.deviation import (
    ConsensusOverweightRecord,
    ConsensusOverweightsResponse,
    DeviationHistoryRecord,
    DeviationHistoryResponse,
    DeviationRecord,
    DeviationResponse,
    StockHolderRecord,
    StockHoldersResponse,
)
from app.schemas.fund import (
    BenchmarkShort,
    FundDetailResponse,
    FundListResponse,
    FundResponse,
    TopDeviation,
)
from app.schemas.holdings import HoldingRecord, HoldingsSnapshotResponse
from app.schemas.pipeline import (
    DataFreshness,
    PipelineHealth,
    PipelineRunResponse,
    PipelineTriggerRequest,
    ScheduleInfo,
)

__all__ = [
    "BacktestConfigSchema",
    "BacktestMetrics",
    "BacktestResultSchema",
    "BenchmarkHoldingRecord",
    "BenchmarkHoldingsResponse",
    "BenchmarkResponse",
    "BenchmarkShort",
    "ConsensusOverweightRecord",
    "ConsensusOverweightsResponse",
    "CursorPagination",
    "DataFreshness",
    "DeviationHistoryRecord",
    "DeviationHistoryResponse",
    "DeviationRecord",
    "DeviationResponse",
    "EquityCurvePoint",
    "ErrorResponse",
    "FundDetailResponse",
    "FundListResponse",
    "FundResponse",
    "HoldingRecord",
    "HoldingsSnapshotResponse",
    "MonthlyReturn",
    "PipelineHealth",
    "PipelineRunResponse",
    "PipelineTriggerRequest",
    "PrecomputedStrategySchema",
    "ScheduleInfo",
    "StockHolderRecord",
    "StockHoldersResponse",
    "TopDeviation",
]
