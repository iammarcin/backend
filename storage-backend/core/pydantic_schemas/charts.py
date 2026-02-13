"""Chart and visualization schemas for agentic chart generation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================================
# Enums and Constants
# ============================================================================


class ChartType(str, Enum):
    """Supported chart types."""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    MERMAID = "mermaid"


class DataSource(str, Enum):
    """Data source identifiers."""

    GARMIN = "garmin_db"
    BLOOD = "blood_db"
    UFC = "ufc_db"
    SEARCH = "semantic_search"
    GENERATED = "llm_generated"


DEFAULT_COLORS: List[str] = [
    "#3B82F6",  # Blue
    "#10B981",  # Green
    "#F59E0B",  # Amber
    "#EF4444",  # Red
    "#8B5CF6",  # Purple
    "#EC4899",  # Pink
    "#06B6D4",  # Cyan
    "#F97316",  # Orange
]

MERMAID_THEME = "default"


# ============================================================================
# Data Models
# ============================================================================


class DataPoint(BaseModel):
    """Individual data point for scatter plots or custom positioning."""

    x: Union[str, float, int] = Field(
        ..., description="X-axis value (category or number)"
    )
    y: float = Field(..., description="Y-axis value")
    label: Optional[str] = Field(None, description="Optional label for this point")


class Dataset(BaseModel):
    """A single data series within a chart."""

    label: str = Field(..., description="Name of this data series")
    data: Union[List[float], List[int], List[DataPoint]] = Field(
        ..., description="Array of values or data points"
    )
    color: Optional[str] = Field(None, description="Hex color for this series")


class ChartData(BaseModel):
    """Data structure for data-based charts (bar, line, pie, area, scatter)."""

    datasets: List[Dataset] = Field(..., description="One or more data series")
    labels: Optional[List[str]] = Field(
        None, description="X-axis labels for categorical data"
    )


class ChartOptions(BaseModel):
    """Display and interactivity options for charts."""

    interactive: bool = Field(True, description="Enable hover, tooltips, zoom")
    show_legend: bool = Field(True, description="Display legend")
    show_grid: bool = Field(True, description="Display grid lines")
    colors: Optional[List[str]] = Field(
        None, description="Custom color palette (overrides dataset colors)"
    )
    x_axis_label: Optional[str] = Field(None, description="Label for X-axis")
    y_axis_label: Optional[str] = Field(None, description="Label for Y-axis")
    stacked: bool = Field(False, description="Stack multiple datasets (bar, area)")
    show_values: bool = Field(False, description="Display values on chart")


# ============================================================================
# Chart Payload - Main Contract
# ============================================================================


class ChartPayload(BaseModel):
    """Chart payload sent to frontends via customEvent."""

    chart_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this chart",
    )
    chart_type: ChartType = Field(..., description="Type of visualization")
    title: str = Field(..., description="Chart title")
    subtitle: Optional[str] = Field(None, description="Optional subtitle")
    data: Optional[ChartData] = Field(
        None, description="Chart data (required for non-mermaid charts)"
    )
    mermaid_code: Optional[str] = Field(
        None, description="Mermaid syntax (required for mermaid chart_type)"
    )
    options: ChartOptions = Field(
        default_factory=ChartOptions, description="Display and interactivity options"
    )
    data_source: Optional[DataSource] = Field(
        None, description="Where the data came from"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When this chart was generated"
    )

    model_config = ConfigDict()

    @model_validator(mode="after")
    def validate_chart_payload(self) -> "ChartPayload":
        """Ensure chart payload contains required content per chart type."""
        if self.chart_type == ChartType.MERMAID:
            if not self.mermaid_code:
                raise ValueError("mermaid_code is required for mermaid chart type")
        else:
            if not self.data:
                raise ValueError(f"data is required for {self.chart_type} chart type")
        return self


# ============================================================================
# Tool Input Models
# ============================================================================


class TimeRange(BaseModel):
    """Time range specification for data queries."""

    start: Optional[datetime] = Field(None, description="Start of time range")
    end: Optional[datetime] = Field(None, description="End of time range")
    last_n_days: Optional[int] = Field(None, description="Alternative: last N days")
    last_n_weeks: Optional[int] = Field(None, description="Alternative: last N weeks")
    last_n_months: Optional[int] = Field(
        None, description="Alternative: last N months"
    )
    all_time: Optional[bool] = Field(None, description="Fetch all available data regardless of date range")


class DataQuery(BaseModel):
    """Query specification for fetching real data from internal sources."""

    source: DataSource = Field(..., description="Which data source to query")
    metric: str = Field(..., description="Metric to fetch (e.g., heart_rate)")
    time_range: Optional[TimeRange] = Field(
        None, description="Time period for the data"
    )
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")
    aggregation: Optional[str] = Field(
        None, description="Aggregation level: daily, weekly, monthly, none"
    )
    limit: int = Field(
        100, ge=1, le=1000, description="Maximum number of data points to return"
    )


class ChartToolInput(BaseModel):
    """Input schema for the chart generation tool."""

    chart_type: ChartType = Field(..., description="Type of chart to generate")
    title: str = Field(..., description="Title for the chart")
    subtitle: Optional[str] = Field(None, description="Optional subtitle")
    data: Optional[ChartData] = Field(
        None, description="Direct data for the chart (synthetic/generated)"
    )
    data_query: Optional[DataQuery] = Field(
        None, description="Query to fetch real data from internal sources"
    )
    mermaid_code: Optional[str] = Field(
        None, description="Mermaid diagram syntax for flowcharts/diagrams"
    )
    options: Optional[ChartOptions] = Field(
        None, description="Chart display options from the LLM"
    )
