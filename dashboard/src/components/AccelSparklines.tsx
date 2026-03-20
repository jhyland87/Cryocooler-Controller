import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import type { DataPoint } from '../types/telemetry';
import { SparkCard } from './SparkCard';
import { MultiSparkCard } from './MultiSparkCard';
import { VibrationWave } from './VibrationWave';
import * as sx from '../theme/styles';

interface Props {
  accelX:   DataPoint[];
  accelY:   DataPoint[];
  accelZ:   DataPoint[];
  accelMag: DataPoint[];
  freqHz:   DataPoint[];
  motion:   number | undefined;
}

export function AccelSparklines({ accelX, accelY, accelZ, accelMag, freqHz, motion }: Props) {
  return (
    <Box>
      {/* Motion chip */}
      <Box sx={sx.motionChipWrapper}>
        <Chip
          label={motion ? 'MOTION' : 'STILL'}
          size="small"
          sx={sx.motionChip(Boolean(motion))}
        />
      </Box>

      <Box sx={sx.accelGrid}>
        <Box sx={sx.gridCell}>
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
        <Box sx={sx.gridCell}><SparkCard label="Magnitude" data={accelMag} color="#ffa726" unit="m/s²" dp={3} /></Box>
        <Box sx={sx.gridCell}><SparkCard label="Vibration" data={freqHz} color="#ab47bc" unit="Hz" dp={1} /></Box>
        <Box sx={sx.gridCell}><VibrationWave accelMag={accelMag} freqHz={freqHz} /></Box>
      </Box>
    </Box>
  );
}
