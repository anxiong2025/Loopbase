"""旅行攻略领域包；依赖通用 loopbase 内核，内核不反向依赖本包。"""

from .prompts import build_system_prompt

__all__ = ["build_system_prompt"]
