import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';

// ─── Public API ───────────────────────────────────────────────────────────────

export interface SparkCardProps {
  label: string;
  data:  DataPoint[];
  color: string;
  /** Unit suffix appended directly after the formatted value (e.g. "%", "°"). */
  unit:  string;
  /** Decimal places for the current-value label. Default: 1 */
  dp?:   number;
  /**
   * When provided, a LinearProgress gauge bar is rendered between the header
   * row and the sparkline.  Enables warning-colour styling when the latest
   * value exceeds `warnAbove`.
   */
  gauge?: {
    /** Scale ceiling for the progress bar.  Default: 100 */
    max?:       number;
    /** Activates warning styling when `last > warnAbove`. */
    warnAbove?: number;
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * SparkCard
 *
 * Shared card shell used by AccelSparklines (plain sparkline) and
 * SystemSparklines (sparkline + LinearProgress gauge).  Callers opt into the
 * gauge by passing the `gauge` prop; without it the component behaves exactly
 * like the old `SparkItem`.
 */
export function SparkCard({ label, data, color, unit, dp = 1, gauge }: SparkCardProps) {
  const values = data.map((p) => p.v);
  const last   = values.length > 0 ? values[values.length - 1] : null;

  const warn        = gauge?.warnAbove !== undefined && last !== null && last > gauge.warnAbove;
  const activeColor = warn ? '#ffa726' : color;

  const pct = gauge
    ? (last !== null ? Math.min(100, (last / (gauge.max ?? 100)) * 100) : 0)
    : 0;

  // Sparkline is taller when there's no gauge bar.
  const chartHeight = gauge ? 40 : 50;

  return (
    <Box
      sx={{
        flex: '1 1 140px',
        minWidth: 120,
        bgcolor: 'background.paper',
        borderRadius: 1,
        p: 1.5,
        border: '1px solid',
        borderColor: warn ? 'warning.dark' : 'divider',
      }}
    >
      {/* ── Header: label + current value ──────────────────────────────── */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, fontSize: '0.65rem' }}
        >
          {label}
        </Typography>
        {last !== null && (
          <Typography
            variant="caption"
            sx={{ color: warn ? 'warning.light' : color, fontWeight: 700, fontSize: '0.75rem' }}
          >
            {last.toFixed(dp)}{unit}
          </Typography>
        )}
      </Box>

      {/* ── Gauge bar (optional) ───────────────────────────────────────── */}
      {gauge && (
        <LinearProgress
          variant="determinate"
          value={pct}
          sx={{
            mb: 0.75,
            height: 4,
            borderRadius: 2,
            bgcolor: 'action.disabledBackground',
            '& .MuiLinearProgress-bar': { bgcolor: warn ? 'warning.main' : color },
          }}
        />
      )}

      {/* ── Sparkline ──────────────────────────────────────────────────── */}
      <SparkLineChart
        data={values.length > 0 ? values : [0]}
        height={chartHeight}
        colors={[activeColor]}
        showHighlight
        showTooltip
        sx={{ '& .MuiLineElement-root': { strokeWidth: 1.5 } }}
      />
    </Box>
  );
}
