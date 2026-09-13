"""Python 后端应用入口：创建 FastAPI 应用、注册路由与 CORS。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    chat_controller,
    document_controller,
    provider_controller,
    trace_controller,
)
from app.config.settings import CORS_ALLOWED_ORIGINS

app = FastAPI(title="Greenbean Study Assistant API")

# 前端 dev server（vite 固定 5173）与 Tauri 壳都从**别的 origin** 发起请求，必须放行。
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册文档上传解析的路由
app.include_router(document_controller.router, prefix="/api")

# 注册聊天（提问 → 检索 → 带来源回答）的路由
app.include_router(chat_controller.router, prefix="/api")

# 注册结构化 trace 的查询路由（GET /api/traces/{trace_id}）
app.include_router(trace_controller.router, prefix="/api")

# 注册模型配置路由（/api/providers）：没有它，界面就没有任何办法激活一个模型
app.include_router(provider_controller.router, prefix="/api")
