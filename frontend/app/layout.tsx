import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Team AI Research Copilot',
  description: '团队协作科研论文追踪、深度解读与灵感孵化工作台',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased min-h-screen">{children}</body>
    </html>
  );
}
