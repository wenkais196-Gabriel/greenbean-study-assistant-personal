from pydantic import BaseModel, Field

from app.enums.route_types import RouteType


class RoutingDecision(BaseModel):
    """
    用于验证 Agent 结构化输出的数据模型。
    """

    route: RouteType = Field(description="为当前问题选择的路由分类")
    reason: str = Field(description="用简短的语言解释选择该路由分类的理由")
    degraded: bool = Field(
        default=False, description="是否为降级结果（调用 API 失败时回退到 COMPREHENSIVE）。"
    )
