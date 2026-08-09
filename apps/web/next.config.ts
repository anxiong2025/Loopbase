import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 避免 Next.js 左下角开发指示器遮挡侧栏账户头像；编译与运行时错误仍会正常展示。
  devIndicators: false,
  // 关闭：dev 下的双重 effect 调用会让研报生成（真实 LLM + Alpha Vantage 调用，
  // 后者每日额度只有 25 次）跑两遍。cleanup 里已经正确处理了取消，
  // 这里只是不想在本地调试时白白烧掉本就稀缺的额度。
  reactStrictMode: false,
};

export default nextConfig;
