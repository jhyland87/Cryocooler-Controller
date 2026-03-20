import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import * as sx from '../theme/styles';

// ─── Public API ───────────────────────────────────────────────────────────────

export interface SeriesConfig {
  label: string;
  data:  DataPoint[];
  color: string;
}

export interface MultiSparkCardProps {
  label:  string;
  series: SeriesConfig[];
  unit:   string;
  dp?:    number;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function MultiSparkCard({ label, series, unit, dp = 1 }: MultiSparkCardProps) {
  return (
    <Box sx={sx.sparkCardRoot}>
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <Box sx={sx.cardHeader}>
        <Typography variant="caption" sx={sx.sectionLabel}>
          {label}
        </Typography>
      </Box>

      {/* ── Legend chips ───────────────────────────────────────────────────── */}
      <Box sx={sx.legendChipRow}>
        {series.map((s) => {
          const last = s.data.length > 0 ? s.data[s.data.length - 1].v : null;
          return (
            <Box key={s.label} sx={sx.legendChipItem}>
              <Box sx={sx.legendDot(s.color)} />
              <Typography variant="caption" sx={sx.legendChipLabel}>
                {s.label}
              </Typography>
              <Typography variant="caption" sx={sx.legendChipValue(s.color)}>
                {last !== null ? `${last.toFixed(dp)}${unit}` : '—'}
              </Typography>
            </Box>
          );
        })}
      </Box>

      {/* ── Stacked sparklines ────────────────────────────────────────────── */}
      <Box sx={sx.overlayContainer}>
        {series.map((s, i) => {
          const values = s.data.map((p) => p.v);
          return (
            <Box key={s.label} sx={sx.overlayLayer(i === 0)}>
              <SparkLineChart
                data={values.length > 0 ? values : [0]}
                height={60}
                colors={[s.color]}
                sx={sx.sparklineOverlayStyles}
              />
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
