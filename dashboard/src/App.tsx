import { useState, useEffect, useCallback } from 'preact/hooks';
import CircularProgress from '@mui/material/CircularProgress';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { ThemeProvider } from '@mui/material/styles';
import { theme } from './theme/theme';
import * as sx from './theme/styles';
import { useTelemetry } from './hooks/useTelemetry';
import { useHistoryBuffer } from './hooks/useHistoryBuffer';
import { useFaultHistory } from './hooks/useFaultHistory';
import { Header } from './components/Header';
import { StatusPanel } from './components/StatusPanel';
import { FaultHistoryPanel } from './components/FaultHistoryPanel';
import { TemperatureChart } from './components/TemperatureChart';
import { PowerChart } from './components/PowerChart';
import { CoolingChart } from './components/CoolingChart';
import { AccelSparklines } from './components/AccelSparklines';
import { SystemSparklines } from './components/SystemSparklines';
import { ConsoleLog } from './components/ConsoleLog';
import { CollapsiblePanel } from './components/CollapsiblePanel';
import type { TelemetryData } from './types/telemetry';
import { getField } from './types/telemetry';

// ─── History buffer keys ──────────────────────────────────────────────────────

const HISTORY_KEYS = [
  'cold_head.temp_c',
  'cold_head.ambient_temp_c',
  'cold_head.voltage_v',
  'cold_head.current_a',
  'amplifier.power_w',
  'system.voltage_v',
  'system.current_a',
  'cooling.fan_speed',
  'cooling.temp_c',
  'cooling.flow_rate_lpm',
  'imu.x',
  'imu.y',
  'imu.z',
  'imu.accel_mag',
  'imu.freq_hz',
  'system.cpu_usage_percent',
  'system.heap_usage_percent',
  'system.psram_usage_percent',
] as const;

// ─── Quick-read tile data ─────────────────────────────────────────────────────

interface TileConfig {
  label: string;
  key:   string;
  unit:  string;
  dp:    number;
  color: string;
}

const TILES: TileConfig[] = [
  { label: 'Cold Head', key: 'cold_head.temp_c',         unit: '°C',   dp: 2, color: '#29b6f6' },
  { label: 'Ambient',   key: 'cold_head.ambient_temp_c', unit: '°C',   dp: 2, color: '#ffa726' },
  { label: 'Cool Rate', key: 'cold_head.cooling_rate',   unit: '°C/min',dp: 3, color: '#80cbc4' },
  { label: 'Sys V',     key: 'system.voltage_v',          unit: 'V',    dp: 2, color: '#ce93d8' },
  { label: 'Sys A',     key: 'system.current_a',         unit: 'A',    dp: 2, color: '#f48fb1' },
  { label: 'Sys W',     key: 'system.power_w',           unit: 'W',    dp: 1, color: '#ffcc80' },
  { label: 'Fan Speed', key: 'cooling.fan_speed',        unit: '%',    dp: 0, color: '#4dd0e1' },
];

// ─── App ──────────────────────────────────────────────────────────────────────

export function App() {
  const { data, status, frameCount, onData, onFaultHistory } = useTelemetry();
  const { push, getHistory }                                  = useHistoryBuffer([...HISTORY_KEYS]);
  const { faults, loading: faultsLoading, pushUpdate }        = useFaultHistory();

  const [tick, setTick] = useState(0);

  const handleFrame = useCallback((d: TelemetryData, ts: number) => {
    push(d, ts);
    setTick((n) => n + 1);
  }, [push]);

  useEffect(() => {
    onData(handleFrame);
  }, [onData, handleFrame]);

  useEffect(() => {
    onFaultHistory(pushUpdate);
  }, [onFaultHistory, pushUpdate]);

  // ── Loading screen ──────────────────────────────────────────────────────────

  if (frameCount === 0) {
    const loadingMsg =
      status === 'disconnected'
        ? 'Unable to reach device — retrying…'
        : 'Waiting for first telemetry frame…';

    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={sx.loadingScreen}>
          <CircularProgress size={52} thickness={3.5} />
          <Typography variant="h6" color="text.secondary" sx={sx.loadingTitle}>
            Loading Dashboard
          </Typography>
          <Typography variant="caption" color="text.disabled">
            {loadingMsg}
          </Typography>
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={sx.appShell}>

        {/* ── Header / status bar ────────────────────────────────────────── */}
        <Header
          connectionStatus={status}
          stateName={String(data.state?.name ?? '—')}
          statusText={String(data.state?.status_text ?? '')}
          onDuration={String(data.status?.on_duration ?? '')}
          timeInState={String(data.status?.time_in_state ?? '')}
          cooldownPct={typeof data.cold_head?.cooldown_pct === 'number' ? data.cold_head.cooldown_pct : undefined}
          frameCount={frameCount}
        />

        {/* ── Main content ───────────────────────────────────────────────── */}
        <Box sx={sx.mainContent}>

          {/* ── Connection-lost overlay ─────────────────────────────────── */}
          {status === 'disconnected' && (
            <Box sx={sx.disconnectedOverlay}>
              <CircularProgress size={40} thickness={3} />
              <Typography variant="h6" color="text.secondary" sx={sx.disconnectedTitle}>
                Connection Lost
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Unable to reach device — reconnecting…
              </Typography>
            </Box>
          )}

          <Grid container spacing={2}>

            {/* ── Row 1: Status panel ──────────────────────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 6, lg: 6 }}>
              <CollapsiblePanel title="Status & Indicators">
                <StatusPanel data={data} key={tick} />
              </CollapsiblePanel>
              <Box sx={sx.faultHistorySpacer}>
                <CollapsiblePanel
                  title="Fault History"
                  defaultExpanded={false}
                  expanded={faults.some((f) => f.active) ? true : undefined}
                >
                  <FaultHistoryPanel faults={faults} loading={faultsLoading} />
                </CollapsiblePanel>
              </Box>
            </Grid>

            {/* ── Row 1 right: quick-read numeric tiles ────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 6, lg: 6 }}>
              <CollapsiblePanel title="Quick Read">
                <Box sx={sx.quickReadContainer}>
                  {TILES.map(({ label, key, unit, dp, color }) => {
                    const value = getField(data, key);
                    return (
                      <Box key={`${label}-${unit}`} sx={sx.quickReadTile}>
                        <Typography sx={sx.tileValueColored(color)}>
                          {typeof value === 'number' ? value.toFixed(dp) : '—'}
                        </Typography>
                        <Typography variant="caption" sx={sx.tileUnit}>
                          {unit}
                        </Typography>
                        <Typography variant="caption" sx={sx.tileLabel}>
                          {label}
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
              </CollapsiblePanel>
            </Grid>

            {/* ── Row 2: Main line charts ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cold Head Temperature">
                <TemperatureChart
                  actualC={getHistory('cold_head.temp_c')}
                  ambientC={getHistory('cold_head.ambient_temp_c')}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Power Consumption">
                <PowerChart
                  coldHeadVolts={getHistory('cold_head.voltage_v')}
                  coldHeadAmps={getHistory('cold_head.current_a')}
                  coldHeadWatts={getHistory('amplifier.power_w')}
                  systemVolts={getHistory('system.voltage_v')}
                  systemAmps={getHistory('system.current_a')}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12 }}>
              <CollapsiblePanel title="Cooling System">
                <CoolingChart
                  fanSpeed={getHistory('cooling.fan_speed')}
                  coolantTemp={getHistory('cooling.temp_c')}
                  flowRate={getHistory('cooling.flow_rate_lpm')}
                />
              </CollapsiblePanel>
            </Grid>

            {/* ── Row 3: Sparkline panels ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 7 }}>
              <CollapsiblePanel title="Accelerometer">
                <AccelSparklines
                  accelX={getHistory('imu.x')}
                  accelY={getHistory('imu.y')}
                  accelZ={getHistory('imu.z')}
                  accelMag={getHistory('imu.accel_mag')}
                  freqHz={getHistory('imu.freq_hz')}
                  motion={typeof data.imu?.motion === 'number' ? data.imu.motion : undefined}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 5 }}>
              <CollapsiblePanel title="System Resources">
                <SystemSparklines
                  cpuUsage={getHistory('system.cpu_usage_percent')}
                  heapUsage={getHistory('system.heap_usage_percent')}
                  psramUsage={getHistory('system.psram_usage_percent')}
                />
              </CollapsiblePanel>
            </Grid>

            {/* ── Console log panel ─────────────────────────────────────── */}
            <Grid size={{ xs: 12 }}>
              <CollapsiblePanel title="Console">
                <ConsoleLog logEpoch={data.log_epoch} />
              </CollapsiblePanel>
            </Grid>

          </Grid>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
