import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import * as sx from '../theme/styles';

// ─── Public API ───────────────────────────────────────────────────────────────

export interface SparkCardProps {
  label: string;
  data:  DataPoint[];
  color: string;
  unit:  string;
  dp?:   number;
  gauge?: {
    max?:       number;
    warnAbove?: number;
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

export function SparkCard({ label, data, color, unit, dp = 1, gauge }: SparkCardProps) {
  const values = data.map((p) => p.v);
  const last   = values.length > 0 ? values[values.length - 1] : null;

  const warn        = gauge?.warnAbove !== undefined && last !== null && last > gauge.warnAbove;
  const activeColor = warn ? '#ffa726' : color;

  const pct = gauge
    ? (last !== null ? Math.min(100, (last / (gauge.max ?? 100)) * 100) : 0)
    : 0;

  const chartHeight = gauge ? 40 : 50;

  return (
    <Box sx={sx.sparkCardWarn(warn)}>

      {/* ── Header: label + current value ──────────────────────────────── */}
      <Box sx={sx.cardHeader}>
        <Typography variant="caption" sx={sx.sectionLabel}>
          {label}
        </Typography>
        {last !== null && (
          <Typography
            variant="caption"
            sx={sx.sparkCurrentValue(warn, color)}
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
          sx={sx.sparkGaugeBarWithColor(warn, color)}
        />
      )}

      {/* ── Sparkline ──────────────────────────────────────────────────── */}
      <SparkLineChart
        data={values.length > 0 ? values : [0]}
        height={chartHeight}
        colors={[activeColor]}
        showHighlight
        showTooltip
        sx={sx.sparklineStroke}
      />
    </Box>
  );
}
