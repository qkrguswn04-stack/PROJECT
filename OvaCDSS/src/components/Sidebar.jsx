'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/screening', label: '환자목록'    },
  { href: '/pacs',      label: '초음파'      },
  { href: '/cdss',      label: '최종분석결과' },
  { href: '/reports',   label: '의뢰서'     },
  { href: '/rmi',       label: 'RMI 계산기' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-60 min-h-screen bg-surface-1 border-r border-hairline flex flex-col shrink-0">

      {/* 로고 */}
      <Link
        href="/screening"
        className="px-5 h-16 border-b border-hairline flex items-center gap-2.5 hover:bg-surface-2 transition-colors"
      >
        <div className="w-6 h-6 bg-primary rounded-[4px] flex items-center justify-center shrink-0">
          <div className="w-2 h-2 bg-white rounded-full" />
        </div>
        <div className="text-xl font-bold text-ink tracking-tight">OVA-LINK</div>
      </Link>

      {/* 네비게이션 */}
      <nav className="flex-1 px-2.5 py-3 space-y-0.5">
        {NAV_ITEMS.map(({ href, label }) => {
          const isActive = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center justify-center px-3 py-2 rounded-lg text-base transition-colors ${
                isActive
                  ? 'bg-primary text-white font-medium'
                  : 'text-ink-subtle hover:text-ink hover:bg-surface-2'
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>

    </div>
  );
}
