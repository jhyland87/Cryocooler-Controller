import { useState } from 'preact/hooks';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import type { FaultRecord } from '../types/faultHistory';

interface Props {
  faults:  FaultRecord[];
  loading: boolean;
}

const PAGE_SIZE = 4;

/** Format a Unix epoch (seconds) into a compact local time string. */
function fmtTime(epoch: number): string {
  if (!epoch) return '—';
  const d = new Date(epoch * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function FaultHistoryPanel({ faults, loading }: Props) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(faults.length / PAGE_SIZE));

  // Clamp page if faults array shrinks (e.g. after a reinit)
  const safePage = Math.min(page, totalPages - 1);
  if (safePage !== page) setPage(safePage);

  const start = safePage * PAGE_SIZE;
  const visible = faults.slice(start, start + PAGE_SIZE);

  return (
    <Box>
      {loading && (
        <Typography variant="body2" color="text.disabled">Loading...</Typography>
      )}

      {!loading && faults.length === 0 && (
        <Typography variant="body2" color="text.disabled">No faults recorded</Typography>
      )}

      {!loading && faults.length > 0 && (
        <>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
            {visible.map((f, i) => (
              <Box
                key={`${f.entered_ms}-${start + i}`}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  px: 1.25,
                  py: 0.75,
                  borderRadius: 0.75,
                  borderLeft: '3px solid',
                  borderLeftColor: f.active ? 'error.main' : 'success.light',
                  bgcolor: f.active ? 'rgba(239,83,80,0.06)' : 'action.hover',
                  fontSize: '0.75rem',
                  overflow: 'hidden',
                }}
              >
                {/* Reason */}
                <Typography
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    fontSize: '0.72rem',
                    color: f.active ? 'error.main' : 'text.primary',
                    minWidth: 0,
                    flexShrink: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={f.reason || 'Unknown'}
                >
                  {f.reason || 'Unknown'}
                </Typography>

                {/* Entered time */}
                <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap', flexShrink: 0 }}>
                  {fmtTime(f.entered_epoch)}
                </Typography>

                {/* Arrow */}
                <Typography variant="caption" sx={{ color: 'text.disabled', flexShrink: 0 }}>→</Typography>

                {/* Cleared time or ACTIVE badge */}
                {f.active ? (
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 700,
                      color: '#fff',
                      bgcolor: 'error.main',
                      px: 0.75,
                      py: 0.15,
                      borderRadius: 0.5,
                      fontSize: '0.62rem',
                      letterSpacing: 0.5,
                      flexShrink: 0,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    ACTIVE
                  </Typography>
                ) : (
                  <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap', flexShrink: 0 }}>
                    {fmtTime(f.cleared_epoch)}
                  </Typography>
                )}

                {/* Cleared by */}
                {!f.active && f.cleared_by && (
                  <Typography variant="caption" sx={{ color: 'text.disabled', fontStyle: 'italic', ml: 'auto', whiteSpace: 'nowrap', flexShrink: 0 }}>
                    {f.cleared_by}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mt: 1.5 }}>
              <IconButton
                size="small"
                disabled={safePage === 0}
                onClick={() => setPage(safePage - 1)}
                sx={{ fontSize: '0.75rem', width: 28, height: 28 }}
              >
                ◀
              </IconButton>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                {safePage + 1} / {totalPages}
              </Typography>
              <IconButton
                size="small"
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage(safePage + 1)}
                sx={{ fontSize: '0.75rem', width: 28, height: 28 }}
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
