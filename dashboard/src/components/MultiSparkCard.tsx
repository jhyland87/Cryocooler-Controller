import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import type { MultiSparkCardProps } from '../types/components';
import * as sx from '../theme/styles';

// ─── Component ────────────────────────────────────────────────────────────────

export function MultiSparkCard({ label, series, unit, dp = 1 }: MultiSparkCardProps) {
  const loading = series.every((s) => s.data.length === 0);

  if (loading) {
    return (
      <Box sx={sx.sparkCardRoot}>
        <Box sx={sx.cardHeader}>
          <Skeleton variant="text" width={90} height={12} />
        </Box>
        <Box sx={sx.legendChipRow}>
          {series.map((s) => (
            <Skeleton key={s.label} variant="text" width={60} height={12} />
          ))}
        </Box>
        <Skeleton variant="rounded" height={60} />
      </Box>
    );
  }

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
          const validPts = s.data.filter((p) => p.v !== null);
          const last = validPts.length > 0 ? validPts[validPts.length - 1].v : null;
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
          const values = s.data.map((p) => p.v).filter((v): v is number => v !== null);
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
