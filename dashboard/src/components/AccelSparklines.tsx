import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import { SparkCard } from './SparkCard';

interface Props {
  accelX:   DataPoint[];
  accelY:   DataPoint[];
  accelZ:   DataPoint[];
  accelMag: DataPoint[];
  motion:   number | undefined;
}

export function AccelSparklines({ accelX, accelY, accelZ, accelMag, motion }: Props) {
  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography
          variant="subtitle2"
          sx={{ color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}
        >
          Accelerometer
        </Typography>
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

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <SparkCard label="Roll"      data={accelX}   color="#ef5350" unit="°"    dp={3} />
        <SparkCard label="Pitch"     data={accelY}   color="#42a5f5" unit="°"    dp={3} />
        <SparkCard label="Yaw"       data={accelZ}   color="#66bb6a" unit="°"    dp={3} />
        <SparkCard label="Magnitude" data={accelMag} color="#ffa726" unit="m/s²" dp={3} />
      </Box>
    </Box>
  );
}
