import { useMemo } from 'preact/hooks';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import * as sx from '../theme/styles';

interface Props {
  accelMag: DataPoint[];
  freqHz: DataPoint[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const WIDTH  = 280;
const HEIGHT = 100;
const MID_Y  = HEIGHT / 2;

const GRAVITY = 9.81;
const MAX_AMP = 3.0;
const REF_HZ    = 60;
const REF_CYCLES = 8;
const MIN_CYCLES = 2;
const MAX_CYCLES = 20;
const AVG_WINDOW = 10;

// ─── Helpers ─────────────────────────────────────────────────────────────────

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
    const amp = Math.min(Math.max((peakMag - GRAVITY) / MAX_AMP, 0), 1) * (MID_Y - 4);

    const cycles = lastFreq > 0
      ? Math.min(MAX_CYCLES, Math.max(MIN_CYCLES, (lastFreq / REF_HZ) * REF_CYCLES))
      : 0;

    if (cycles === 0 || amp < 0.5) {
      return `M0,${MID_Y} L${WIDTH},${MID_Y}`;
    }

    const steps = Math.max(200, Math.round(cycles * 30));
    const parts: string[] = [];
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const x = t * WIDTH;
      const y = MID_Y - amp * Math.sin(2 * Math.PI * cycles * t);
      parts.push(i === 0 ? `M${x.toFixed(1)},${y.toFixed(1)}` : `L${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return parts.join(' ');
  }, [peakMag, lastFreq]);

  return (
    <Box sx={sx.vibrationCardRoot}>
      {/* Header */}
      <Box sx={sx.cardHeader}>
        <Typography variant="caption" sx={sx.sectionLabel}>
          Vibration Wave
        </Typography>
        <Typography
          variant="caption"
          sx={sx.vibrationFreqValue}
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
        <line
          x1={0} y1={MID_Y} x2={WIDTH} y2={MID_Y}
          stroke="rgba(0,0,0,0.08)"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
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
