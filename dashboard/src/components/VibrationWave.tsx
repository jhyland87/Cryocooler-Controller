import { useMemo } from 'preact/hooks';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import type { VibrationWaveProps } from '../types/components';
import * as sx from '../theme/styles';

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
  const valid = pts.filter((p) => p.v !== null);
  if (valid.length === 0) return fallback;
  const slice = valid.slice(-n);
  return slice.reduce((mx, p) => ((p.v as number) > mx ? (p.v as number) : mx), slice[0].v as number);
}

// ─── Component ───────────────────────────────────────────────────────────────

export function VibrationWave({ accelMag, freqHz }: VibrationWaveProps) {
  const validAccel = accelMag.filter((p) => p.v !== null);
  const validFreq  = freqHz.filter((p) => p.v !== null);
  const loading = validAccel.length === 0 && validFreq.length === 0;
  const peakMag = trailingMax(accelMag, AVG_WINDOW, GRAVITY);
  const lastFreq = validFreq.length > 0 ? (validFreq[validFreq.length - 1].v as number) : 0;

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

  if (loading) {
    return (
      <Box sx={sx.vibrationCardRoot}>
        <Box sx={sx.cardHeader}>
          <Skeleton variant="text" width={100} height={12} />
          <Skeleton variant="text" width={50} height={12} />
        </Box>
        <Skeleton variant="rounded" height={HEIGHT} />
      </Box>
    );
  }

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
