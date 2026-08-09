"""金融领域包：工具实现、prompt、目标模板。

依赖方向：finance_agent → loopbase。内核保持领域无关，可被任意领域复用。
"""

from .tools import register_all

__all__ = ["register_all"]
