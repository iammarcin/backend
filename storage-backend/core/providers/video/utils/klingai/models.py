"""Data models and enums for KlingAI API."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class KlingAIModel(str, Enum):
    """Available KlingAI video models."""
    # V1 family
    KLING_V1 = "kling-v1"
    KLING_V1_5 = "kling-v1-5"
    KLING_V1_6 = "kling-v1-6"
    # V2 family
    KLING_V2_MASTER = "kling-v2-master"
    KLING_V2_1 = "kling-v2-1"
    KLING_V2_1_MASTER = "kling-v2-1-master"
    KLING_V2_5 = "kling-v2-5"
    KLING_V2_5_TURBO = "kling-v2-5-turbo"
    # V2.6 family - supports native audio generation
    KLING_V2_6 = "kling-v2-6"
    KLING_V2_6_PRO = "kling-v2-6-pro"
    # Omni model - unified generation + editing
    KLING_O1 = "kling-o1"
    KLING_O1_PRO = "kling-o1-pro"


class VideoMode(str, Enum):
    """Video generation mode."""
    STANDARD = "std"  # Cost-effective, faster
    PROFESSIONAL = "pro"  # Higher quality, slower


class AspectRatio(str, Enum):
    """Video aspect ratios."""
    RATIO_16_9 = "16:9"
    RATIO_9_16 = "9:16"
    RATIO_1_1 = "1:1"


class CameraControlType(str, Enum):
    """Camera control types."""
    SIMPLE = "simple"
    DOWN_BACK = "down_back"
    FORWARD_UP = "forward_up"
    RIGHT_TURN_FORWARD = "right_turn_forward"
    LEFT_TURN_FORWARD = "left_turn_forward"


class TaskStatus(str, Enum):
    """KlingAI task status values."""
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    SUCCEED = "succeed"
    FAILED = "failed"


class CameraConfig(BaseModel):
    """Camera movement configuration (for type='simple')."""
    horizontal: float = Field(0.0, ge=-10, le=10, description="Horizontal movement")
    vertical: float = Field(0.0, ge=-10, le=10, description="Vertical movement")
    pan: float = Field(0.0, ge=-10, le=10, description="Pan rotation")
    tilt: float = Field(0.0, ge=-10, le=10, description="Tilt rotation")
    roll: float = Field(0.0, ge=-10, le=10, description="Roll rotation")
    zoom: float = Field(0.0, ge=-10, le=10, description="Zoom level")

    def validate_single_movement(self) -> None:
        """Ensure only one movement parameter is non-zero."""
        non_zero = sum(
            1 for val in [
                self.horizontal, self.vertical, self.pan,
                self.tilt, self.roll, self.zoom
            ]
            if val != 0.0
        )
        if non_zero > 1:
            raise ValueError(
                "Only one camera movement parameter can be non-zero"
            )


class CameraControl(BaseModel):
    """Camera control configuration."""
    type: CameraControlType
    config: Optional[CameraConfig] = None

    def model_post_init(self, __context: Any) -> None:
        """Validate camera control configuration."""
        if self.type == CameraControlType.SIMPLE:
            if not self.config:
                raise ValueError("config is required when type='simple'")
            self.config.validate_single_movement()
        else:
            if self.config:
                raise ValueError(
                    f"config must be None when type='{self.type.value}'"
                )


class Trajectory(BaseModel):
    """Motion trajectory coordinate."""
    x: int = Field(..., description="X coordinate (bottom-left origin)")
    y: int = Field(..., description="Y coordinate (bottom-left origin)")


class DynamicMask(BaseModel):
    """Dynamic brush mask configuration."""
    mask: str = Field(..., description="Mask image URL or Base64")
    trajectories: List[Trajectory] = Field(
        ...,
        min_length=2,
        max_length=77,
        description="Motion trajectory coordinates (2-77 points)"
    )


class MotionBrush(BaseModel):
    """Motion brush configuration."""
    static_mask: Optional[str] = Field(None, description="Static mask URL or Base64")
    dynamic_masks: Optional[List[DynamicMask]] = Field(
        None,
        max_length=6,
        description="Dynamic mask configurations (max 6)"
    )


class TaskResponse(BaseModel):
    """KlingAI task response."""
    code: int
    message: str
    request_id: str
    data: Dict[str, Any]


class VideoResult(BaseModel):
    """Video generation result."""
    id: str
    url: str
    duration: str
