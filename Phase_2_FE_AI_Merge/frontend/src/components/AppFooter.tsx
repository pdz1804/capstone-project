import { cn } from '../lib/utils';

type AppFooterProps = {
  className?: string;
};

/** Global site footer — shown on every authenticated and login screen. */
export default function AppFooter({ className }: AppFooterProps) {
  return (
    <footer
      className={cn(
        'shrink-0 border-t border-slate-200 bg-white py-3 px-4 text-center text-xs text-slate-500',
        className
      )}
      role="contentinfo"
    >
      All rights reserved - 2026 - HCMUT - K2P Team
    </footer>
  );
}
