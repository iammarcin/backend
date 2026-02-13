"""Chart generation request schema for proactive agent."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from core.pydantic_schemas import ChartData, ChartOptions, ChartType, DataQuery


class ChartGenerationRequest(BaseModel):
    """Request from agent to generate and push a chart (server-to-server).

    Supports three data sources (exactly one required):
    - data: Direct chart data (LLM-generated)
    - data_query: Query to fetch from internal databases (Garmin, Blood, etc.)
    - mermaid_code: Mermaid diagram syntax
    """

    user_id: int = Field(..., description="Target user ID")
    session_id: str = Field(..., description="Session ID for WebSocket routing")
    ai_character_name: str = Field(default="sherlock", description="AI character name")

    # Chart specification
    chart_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Custom chart ID for inline placement (e.g., 'hr_7d_trend'). Auto-generated if not provided.",
    )
    chart_type: ChartType = Field(..., description="Type of chart to generate")
    title: str = Field(..., min_length=1, max_length=200, description="Chart title")
    subtitle: Optional[str] = Field(None, max_length=300, description="Optional subtitle")

    # Data sources (exactly one required)
    data: Optional[ChartData] = Field(None, description="Direct chart data")
    data_query: Optional[DataQuery] = Field(None, description="Query for database data")
    mermaid_code: Optional[str] = Field(None, max_length=10000, description="Mermaid diagram syntax")

    # Display options
    options: Optional[ChartOptions] = Field(None, description="Chart display options")

    @model_validator(mode="after")
    def validate_data_source(self) -> "ChartGenerationRequest":
        """Ensure exactly one data source is provided."""
        sources = [
            self.data is not None,
            self.data_query is not None,
            self.mermaid_code is not None,
        ]
        if sum(sources) == 0:
            raise ValueError("Provide one of: data, data_query, or mermaid_code")
        if sum(sources) > 1:
            raise ValueError("Provide only one of: data, data_query, or mermaid_code")

        # Mermaid requires mermaid chart_type
        if self.mermaid_code and self.chart_type != ChartType.MERMAID:
            raise ValueError("mermaid_code requires chart_type='mermaid'")
        if self.chart_type == ChartType.MERMAID and not self.mermaid_code:
            raise ValueError("chart_type='mermaid' requires mermaid_code")

        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "session_id": "abc-123",
                "ai_character_name": "sherlock",
                "chart_type": "line",
                "title": "Heart Rate Trend",
                "data_query": {
                    "source": "garmin_db",
                    "metric": "resting_heart_rate",
                    "time_range": {"last_n_days": 7},
                },
            }
        }
    }


__all__ = ["ChartGenerationRequest"]
