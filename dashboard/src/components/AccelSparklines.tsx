import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import type { DataPoint } from '../types/telemetry';
import { SparkCard } from './SparkCard';
import { MultiSparkCard } from './MultiSparkCard';
import { VibrationWave } from './VibrationWave';

interface Props {
  accelX:   DataPoint[];
  accelY:   DataPoint[];
  accelZ:   DataPoint[];
  accelMag: DataPoint[];
  freqHz:   DataPoint[];
  motion:   number | undefined;
}

/** CSS Grid cell — children fill the cell regardless of their own flex/minWidth. */
const cellSx = {
  minWidth: 0,
  '& > *': { flex: 'none', minWidth: 0, width: '100%' },
} as const;

export function AccelSparklines({ accelX, accelY, accelZ, accelMag, freqHz, motion }: Props) {
  return (
    <Box>
      {/* Motion chip — title is handled by CollapsiblePanel */}
      <Box sx={{ mb: 1 }}>
        <Chip
          label={motion ? 'MOTION' : 'STILL'}
          size="small"
          sx={{
            fontSize: '0.6rem',
            height: 18,
            bgcolor: motion ? 'warning.dark' : 'success.dark',
            color: '#fff',
            fontWeight: 700,
            letterSpacing: 0.8,
          }}
        />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1 }}>
        {/* Top-left: combined X / Y / Z */}
        <Box sx={cellSx}>
          <MultiSparkCard
            label="Accel X / Y / Z"
            series={[
              { label: 'X', data: accelX, color: '#ef5350' },
              { label: 'Y', data: accelY, color: '#42a5f5' },
              { label: 'Z', data: accelZ, color: '#66bb6a' },
            ]}
            unit="m/s²"
            dp={3}
          />
        </Box>
        {/* Top-right: magnitude */}
        <Box sx={cellSx}><SparkCard label="Magnitude" data={accelMag} color="#ffa726" unit="m/s²" dp={3} /></Box>
        {/* Bottom-left: vibration Hz */}
        <Box sx={cellSx}><SparkCard label="Vibration" data={freqHz} color="#ab47bc" unit="Hz" dp={1} /></Box>
        {/* Bottom-right: sine wave visualisation */}
        <Box sx={cellSx}><VibrationWave accelMag={accelMag} freqHz={freqHz} /></Box>
      </Box>
    </Box>
  );
}
