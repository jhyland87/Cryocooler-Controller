import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { FaultRecord } from '../types/faultHistory';

interface Props {
  faults:  FaultRecord[];
  loading: boolean;
}

/** Format a Unix epoch (seconds) into a compact local time string. */
function fmtTime(epoch: number): string {
  if (!epoch) return '—';
  const d = new Date(epoch * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function FaultHistoryPanel({ faults, loading }: Props) {
  return (
    <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 2, border: '1px solid', borderColor: 'divider' }}>
      <Typography
        variant="subtitle2"
        sx={{ mb: 1.5, color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}
      >
        Fault History
      </Typography>

      {loading && (
        <Typography variant="body2" color="text.disabled">Loading...</Typography>
      )}

      {!loading && faults.length === 0 && (
        <Typography variant="body2" color="text.disabled">No faults recorded</Typography>
      )}

      {!loading && faults.length > 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {faults.map((f, i) => (
            <Box
              key={`${f.entered_ms}-${i}`}
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
              }}
            >
              {/* Reason */}
              <Typography
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 600,
                  fontSize: '0.72rem',
                  color: f.active ? 'error.main' : 'text.primary',
                  minWidth: 120,
                }}
              >
                {f.reason || 'Unknown'}
              </Typography>

              {/* Entered time */}
              <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                {fmtTime(f.entered_epoch)}
              </Typography>

              {/* Arrow */}
              <Typography variant="caption" sx={{ color: 'text.disabled' }}>→</Typography>

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
                  }}
                >
                  ACTIVE
                </Typography>
              ) : (
                <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                  {fmtTime(f.cleared_epoch)}
                </Typography>
              )}

              {/* Cleared by */}
              {!f.active && f.cleared_by && (
                <Typography variant="caption" sx={{ color: 'text.disabled', fontStyle: 'italic', ml: 'auto' }}>
                  {f.cleared_by}
                </Typography>
              )}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
