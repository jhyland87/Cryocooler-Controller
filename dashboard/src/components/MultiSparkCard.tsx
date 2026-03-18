import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';

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

/**
 * MultiSparkCard
 *
 * Renders multiple overlaid sparklines inside a single card.
 * Each series gets its own coloured sparkline and a legend chip
 * showing its latest value.
 */
export function MultiSparkCard({ label, series, unit, dp = 1 }: MultiSparkCardProps) {
  return (
    <Box
      sx={{
        flex: '1 1 140px',
        minWidth: 120,
        bgcolor: 'background.paper',
        borderRadius: 1,
        p: 1.5,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, fontSize: '0.65rem' }}
        >
          {label}
        </Typography>
      </Box>

      {/* ── Legend chips ───────────────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 0.5, flexWrap: 'wrap' }}>
        {series.map((s) => {
          const last = s.data.length > 0 ? s.data[s.data.length - 1].v : null;
          return (
            <Box key={s.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: s.color, flexShrink: 0 }} />
              <Typography variant="caption" sx={{ fontSize: '0.62rem', color: 'text.secondary', fontWeight: 600 }}>
                {s.label}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.68rem', color: s.color, fontWeight: 700 }}>
                {last !== null ? `${last.toFixed(dp)}${unit}` : '—'}
              </Typography>
            </Box>
          );
        })}
      </Box>

      {/* ── Stacked sparklines ────────────────────────────────────────────── */}
      <Box sx={{ position: 'relative', height: 60 }}>
        {series.map((s, i) => {
          const values = s.data.map((p) => p.v);
          return (
            <Box
              key={s.label}
              sx={{
                position: i === 0 ? 'relative' : 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
              }}
            >
              <SparkLineChart
                data={values.length > 0 ? values : [0]}
                height={60}
                colors={[s.color]}
                sx={{
                  '& .MuiLineElement-root': { strokeWidth: 1.5 },
                  // Make the area fill transparent so lines underneath show through.
                  '& .MuiAreaElement-root': { opacity: 0 },
                }}
              />
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
