import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, ChevronsUpDown } from 'lucide-react';

export type SortDirection = 'asc' | 'desc';

type AdminSortHeaderProps = {
  label: string;
  active: boolean;
  direction: SortDirection;
  onClick: () => void;
  align?: 'left' | 'right';
};

export function AdminSortHeader({
  label,
  active,
  direction,
  onClick,
  align = 'left',
}: AdminSortHeaderProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'inline-flex items-center gap-1 rounded-md px-1 py-0.5 transition hover:bg-slate-200/70',
        align === 'right' ? 'w-full justify-end' : '',
      ].join(' ')}
      title={`Sort by ${label}`}
      aria-label={`Sort by ${label}`}
    >
      <span>{label}</span>
      {!active ? (
        <ChevronsUpDown className="h-3.5 w-3.5 text-slate-400" />
      ) : direction === 'asc' ? (
        <ChevronUp className="h-3.5 w-3.5 text-sky-700" />
      ) : (
        <ChevronDown className="h-3.5 w-3.5 text-sky-700" />
      )}
    </button>
  );
}

type AdminTablePaginationProps = {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextPageSize: number) => void;
  pageSizeOptions?: number[];
  itemLabel?: string;
};

export function AdminTablePagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  itemLabel = 'rows',
}: AdminTablePaginationProps) {
  const totalPages = Math.max(1, Math.ceil(Math.max(0, totalItems) / Math.max(1, pageSize)));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = totalItems === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = totalItems === 0 ? 0 : Math.min(totalItems, safePage * pageSize);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
      <span>{totalItems === 0 ? `No ${itemLabel}` : `${start}-${end} of ${totalItems} ${itemLabel}`}</span>

      <label className="inline-flex items-center gap-1">
        <span>Rows</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value) || 10)}
          className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
          title="Rows per page"
          aria-label="Rows per page"
        >
          {pageSizeOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        onClick={() => onPageChange(safePage - 1)}
        disabled={safePage <= 1}
        className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        title="Previous page"
        aria-label="Previous page"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </button>

      <span>
        Page {safePage} / {totalPages}
      </span>

      <button
        type="button"
        onClick={() => onPageChange(safePage + 1)}
        disabled={safePage >= totalPages}
        className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        title="Next page"
        aria-label="Next page"
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
