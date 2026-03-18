import { useMemo } from 'preact/hooks';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';

interface Props {
  /** Acceleration magnitude history (m/s²). */
  accelMag: DataPoint[];
  /** Vibration frequency history (Hz). */
  freqHz: DataPoint[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const WIDTH  = 280;
const HEIGHT = 100;
const MID_Y  = HEIGHT / 2;

/** Gravity baseline — magnitude at rest is ~9.81 m/s². */
const GRAVITY = 9.81;

/** Maximum vibration amplitude (above gravity) that maps to full chart height. */
const MAX_AMP = 3.0;

/** Visual cycles to render when frequency is at this reference value. */
const REF_HZ    = 60;
const REF_CYCLES = 8;

/** Minimum / maximum visual cycles so the wave always looks reasonable. */
const MIN_CYCLES = 2;
const MAX_CYCLES = 20;

/** Number of recent samples to average for a smoother wave. */
const AVG_WINDOW = 10;

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Return the max of the last `n` values in a DataPoint array. */
function trailingMax(pts: DataPoint[], n: number, fallback: number): number {
  if (pts.length === 0) return fallback;
  const slice = pts.slice(-n);
  return slice.reduce((mx, p) => (p.v > mx ? p.v : mx), slice[0].v);
}

// ─── Component ───────────────────────────────────────────────────────────────

export function VibrationWave({ accelMag, freqHz }: Props) {
  const peakMag = trailingMax(accelMag, AVG_WINDOW, GRAVITY);
  const lastFreq = freqHz.length > 0 ? freqHz[freqHz.length - 1].v : 0;

  const pathD = useMemo(() => {
    // Amplitude: deviation from gravity, normalised to half the chart height.
    const amp = Math.min(Math.max((peakMag - GRAVITY) / MAX_AMP, 0), 1) * (MID_Y - 4);

    // Number of visual cycles — higher Hz ⇒ more (narrower) cycles.
    const cycles = lastFreq > 0
      ? Math.min(MAX_CYCLES, Math.max(MIN_CYCLES, (lastFreq / REF_HZ) * REF_CYCLES))
      : 0;

    if (cycles === 0 || amp < 0.5) {
      // Flat line when idle.
      return `M0,${MID_Y} L${WIDTH},${MID_Y}`;
    }

    // Build the SVG path — sample enough points for a smooth curve.
    const steps = Math.max(200, Math.round(cycles * 30));
    const parts: string[] = [];
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;                       // 0 → 1
      const x = t * WIDTH;
      const y = MID_Y - amp * Math.sin(2 * Math.PI * cycles * t);
      parts.push(i === 0 ? `M${x.toFixed(1)},${y.toFixed(1)}` : `L${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return parts.join(' ');
  }, [peakMag, lastFreq]);

  return (
    <Box
      sx={{
        flex: '1 1 240px',
        minWidth: 200,
        bgcolor: 'background.paper',
        borderRadius: 1,
        p: 1.5,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, fontSize: '0.65rem' }}
        >
          Vibration Wave
        </Typography>
        <Typography
          variant="caption"
          sx={{ color: '#ab47bc', fontWeight: 700, fontSize: '0.75rem' }}
        >
          {lastFreq > 0 ? `${lastFreq.toFixed(1)} Hz` : '—'}
        </Typography>
      </Box>

      {/* SVG sine wave */}
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        height={HEIGHT}
        preserveAspectRatio="none"
        style={{ display: 'block' }}
      >
        {/* faint centre line */}
        <line
          x1={0} y1={MID_Y} x2={WIDTH} y2={MID_Y}
          stroke="rgba(0,0,0,0.08)"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
        {/* sine wave */}
        <path
          d={pathD}
          fill="none"
          stroke="#ab47bc"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </Box>
  );
}
