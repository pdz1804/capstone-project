import { cn } from '../lib/utils';

type AppFooterProps = {
  className?: string;
};

/** Global site footer   shown on every authenticated and login screen. */
export default function AppFooter({ className }: AppFooterProps) {
  return (
    <footer
      className={cn(
        'shrink-0 border-t border-sky-100/90 bg-white/95 backdrop-blur-sm',
        className
      )}
      role="contentinfo"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs sm:text-sm text-slate-600 text-center sm:text-left font-medium">
          BK-MInD - Educational RAG Platform | CS252 Capstone Project - HCMUT
        </p>
        <div className="flex items-center justify-center sm:justify-end gap-4 text-xs text-slate-500">
          <span className="rounded-full bg-slate-50 px-2.5 py-1 border border-slate-100">Privacy-first</span>
          <span className="rounded-full bg-slate-50 px-2.5 py-1 border border-slate-100">Secure Access</span>
          <span className="rounded-full bg-slate-50 px-2.5 py-1 border border-slate-100">2026 K2P Team</span>
        </div>
      </div>
    </footer>
  );
}
