import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useMemo, useState, useCallback } from 'preact/hooks';
import type { DataPoint } from '../types/telemetry';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';
import { createTimeFormatter } from '../utils/formatters';

// ─── Public API ───────────────────────────────────────────────────────────────

export interface ChartSeries {
  label: string;
  data:  DataPoint[];
  color: string;
}

export interface TelemetryLineChartProps {
  title:  string;
  series: ChartSeries[];
  /**
   * Y-axis bounds.
   *
   * • Both `min` and `max` present  — fixed domain (e.g. temperature: -200..40).
   * • Only `min` present            — `max` is computed from live data, with a
   *                                   fallback of `1` when all values are zero
   *                                   so the axis never collapses to [0, 0].
   * • Omitted entirely              — fully auto-scaled by MUI.
   */
  yAxis?: {
    min?: number;
    max?: number;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Pad a series array to `len` by prepending nulls (aligns shorter series to
 *  the right when the longest series has earlier data points). */
function padTo(arr: number[], len: number): (number | null)[] {
  const out: (number | null)[] = [...arr];
  while (out.length < len) out.unshift(null);
  return out;
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * TelemetryLineChart
 *
 * Shared rolling time-series chart used by TemperatureChart, PowerChart, and
 * CoolingChart.  Callers supply a title, an array of series configs, and
 * optional y-axis bounds; everything else (x-axis window, time formatter,
 * container-responsive tick step, legend, margins) is handled here.
 */
export function TelemetryLineChart({ title, series, yAxis }: TelemetryLineChartProps) {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());

  const toggleSeries = useCallback((label: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  }, []);

  // Filter to only visible series for rendering and y-axis scaling.
  const visibleSeries = series.filter((s) => !hidden.has(s.label));

  // Use whichever series is longest as the shared x-axis source (from ALL
  // series so the x-axis stays stable when toggling).
  const longest = series.reduce<DataPoint[]>(
    (best, s) => (s.data.length >= best.length ? s.data : best),
    [],
  );

  const xData        = longest.map((p) => p.t);
  const timeFormatter = useMemo(() => createTimeFormatter(), [xData.length > 0 ? xData[0] : 0]);

  const n    = xData.length || 1;
  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

  // Compute y-axis bounds from VISIBLE series only so the chart auto-scales
  // to just the data the user has selected.  When some series are hidden, we
  // let MUI auto-scale even if the caller provided fixed bounds — this gives
  // the best zoom experience when toggling series on/off.
  const someHidden = hidden.size > 0;

  const yMin: number | undefined = (() => {
    if (visibleSeries.length === 0) return yAxis?.min ?? 0;
    if (!someHidden && yAxis?.min !== undefined) return yAxis.min;
    // Auto-scale: let MUI pick, but anchor at caller's min if provided.
    return yAxis?.min !== undefined ? undefined : undefined;
  })();

  const yMax: number | undefined = (() => {
    if (visibleSeries.length === 0) return yAxis?.max ?? 1;
    if (!someHidden && yAxis?.max !== undefined) return yAxis.max;
    // Auto-scale from visible data only.
    const allValues = visibleSeries.flatMap((s) => s.data.map((p) => p.v));
    const raw = allValues.length > 0 ? Math.max(0, ...allValues) : 0;
    return raw > 0 ? undefined : 1;
  })();

  const chartSeries = visibleSeries.map((s) => ({
    label:    s.label,
    data:     padTo(s.data.map((p) => p.v), n),
    color:    s.color,
    showMark: false,
  }));

  return (
    <Box ref={containerRef} sx={{ width: '100%', height: 280 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5, gap: 1, flexWrap: 'wrap' }}>
        <Typography
          variant="subtitle2"
          sx={{
            color: 'text.secondary',
            fontWeight: 600,
            letterSpacing: 1,
            textTransform: 'uppercase',
            fontSize: '0.7rem',
            mr: 1,
          }}
        >
          {title}
        </Typography>
        {series.map((s) => {
          const isVisible = !hidden.has(s.label);
          return (
            <Box
              key={s.label}
              onClick={() => toggleSeries(s.label)}
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                userSelect: 'none',
                px: 0.75,
                py: 0.25,
                borderRadius: 1,
                border: '1px solid',
                borderColor: isVisible ? s.color : 'divider',
                opacity: isVisible ? 1 : 0.4,
                transition: 'opacity 0.15s, border-color 0.15s',
                '&:hover': { opacity: isVisible ? 0.85 : 0.6 },
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: isVisible ? s.color : 'text.disabled',
                }}
              />
              <Typography sx={{ fontSize: '0.65rem', color: isVisible ? 'text.primary' : 'text.disabled' }}>
                {s.label}
              </Typography>
            </Box>
          );
        })}
      </Box>

      <LineChart
        xAxis={[{
          data:           xData.length > 0 ? xData : [xMax],
          min:            xMin,
          max:            xMax,
          scaleType:      'linear',
          valueFormatter: timeFormatter,
          tickMinStep:    tickStep,
        }]}
        yAxis={[{
          min:            yMin,
          max:            yMax,
          valueFormatter: (v: number) => v % 1 === 0 ? String(v) : v.toFixed(1),
        }]}
        series={chartSeries}
        height={220}
        skipAnimation
        slotProps={{ legend: { hidden: true } }}
        margin={{ top: 10, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
