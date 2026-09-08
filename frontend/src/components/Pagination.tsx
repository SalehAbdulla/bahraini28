interface PaginationProps {
  page: number;
  pages: number;
  onPage: (page: number) => void;
}

export default function Pagination({ page, pages, onPage }: PaginationProps) {
  if (pages <= 1) return null;
  return (
    <nav className="mt-8 flex items-center justify-center gap-3">
      <button
        className="btn-secondary"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        ← Prev
      </button>
      <span className="text-sm text-slate-500">
        Page {page} of {pages}
      </span>
      <button
        className="btn-secondary"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        Next →
      </button>
    </nav>
  );
}