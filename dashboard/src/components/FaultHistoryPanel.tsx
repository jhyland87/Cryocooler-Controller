import { useState } from 'preact/hooks';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import type { FaultHistoryPanelProps } from '../types/components';
import * as sx from '../theme/styles';

const PAGE_SIZE = 4;

function fmtTime(epoch: number): string {
  if (!epoch) return '—';
  const d = new Date(epoch * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function FaultHistoryPanel({ faults, loading }: FaultHistoryPanelProps) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(faults.length / PAGE_SIZE));

  const safePage = Math.min(page, totalPages - 1);
  if (safePage !== page) setPage(safePage);

  const start = safePage * PAGE_SIZE;
  const visible = faults.slice(start, start + PAGE_SIZE);

  return (
    <Box>
      {loading && (
        <Box sx={sx.faultList}>
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} variant="rounded" height={36} sx={sx.skeletonFaultRow} />
          ))}
        </Box>
      )}

      {!loading && faults.length === 0 && (
        <Typography variant="body2" color="text.disabled">No faults recorded</Typography>
      )}

      {!loading && faults.length > 0 && (
        <>
          <Box sx={sx.faultList}>
            {visible.map((f, i) => (
              <Box key={`${f.entered_ms}-${start + i}`} sx={sx.faultRow(f.active)}>
                {/* Reason */}
                <Typography sx={sx.faultReason(f.active)} title={f.reason || 'Unknown'}>
                  {f.reason || 'Unknown'}
                </Typography>

                {/* Entered time */}
                <Typography variant="caption" sx={sx.faultTimestamp}>
                  {fmtTime(f.entered_epoch)}
                </Typography>

                {/* Arrow */}
                <Typography variant="caption" sx={sx.faultArrow}>→</Typography>

                {/* Cleared time or ACTIVE badge */}
                {f.active ? (
                  <Typography variant="caption" sx={sx.faultActiveBadge}>
                    ACTIVE
                  </Typography>
                ) : (
                  <Typography variant="caption" sx={sx.faultTimestamp}>
                    {fmtTime(f.cleared_epoch)}
                  </Typography>
                )}

                {/* Cleared by */}
                {!f.active && f.cleared_by && (
                  <Typography variant="caption" sx={sx.faultClearedBy}>
                    {f.cleared_by}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <Box sx={sx.faultPagination}>
              <IconButton
                size="small"
                disabled={safePage === 0}
                onClick={() => setPage(safePage - 1)}
                sx={sx.faultPaginationBtn}
              >
                ◀
              </IconButton>
              <Typography variant="caption" sx={sx.faultPageLabel}>
                {safePage + 1} / {totalPages}
              </Typography>
              <IconButton
                size="small"
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage(safePage + 1)}
                sx={sx.faultPaginationBtn}
              >
                ▶
              </IconButton>
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
