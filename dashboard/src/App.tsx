import { useState, useEffect, useCallback, useMemo } from 'preact/hooks';
import CircularProgress from '@mui/material/CircularProgress';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { ThemeProvider } from '@mui/material/styles';
import { theme } from './theme/theme';
import * as sx from './theme/styles';
import { useTelemetry } from './hooks/useTelemetry';
import { HISTORY_WINDOW_MS, useHistoryBuffer } from './hooks/useHistoryBuffer';
import { useFaultHistory } from './hooks/useFaultHistory';
import { useSession } from './hooks/useSession';
import { Header } from './components/Header';
import { StatusPanel } from './components/StatusPanel';
import { FaultHistoryPanel } from './components/FaultHistoryPanel';
import { TemperatureChart } from './components/TemperatureChart';
import { QuickRead } from './components/QuickRead';
import { TelemetryLineChart } from './components/TelemetryLineChart';
import { CoolingChart } from './components/CoolingChart';
import { AccelSparklines } from './components/AccelSparklines';
import { SystemSparklines } from './components/SystemSparklines';
import { ConsoleLog } from './components/ConsoleLog';
import { CollapsiblePanel } from './components/CollapsiblePanel';
import type { TelemetryData } from './types/telemetry';
import type { ChartOverlay, TileGroup } from './types/components';

// ─── History buffer keys ──────────────────────────────────────────────────────

const HISTORY_KEYS = [
  'cold_head.temp_c',
  'cold_head.ambient_temp_c',
  'cold_head.target_temp_c',
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
  'cold_head.cooling_rate',
  'system.power_w',
] as const;

// ─── Quick-read tile data ─────────────────────────────────────────────────────

/** Line / tile colours shared by the Quick Read tiles and the power charts. */
const POWER_COLORS = {
  cryoVolts:   '#ce93d8',
  cryoAmps:    '#f48fb1',
  cryoWatts:   '#ef5350',
  systemVolts: '#80cbc4',
  systemAmps:  '#ffcc80',
  systemWatts: '#a1887f',
};

const TILE_GROUPS: TileGroup[] = [
  {
    title: 'Temperature',
    tiles: [
      { label: 'Cold Head', key: 'cold_head.temp_c',         unit: '°C',     dp: 2, color: '#29b6f6' },
      { label: 'Ambient',   key: 'cold_head.ambient_temp_c', unit: '°C',     dp: 2, color: '#ffa726' },
      { label: 'Cool Rate', key: 'cold_head.cooling_rate',   unit: '°C/min', dp: 3, color: '#80cbc4' },
    ],
  },
  {
    title: 'Cryocooler',
    tiles: [
      { label: 'Volts', key: 'cold_head.voltage_v', unit: 'V', dp: 2, color: POWER_COLORS.cryoVolts },
      { label: 'Amps',  key: 'cold_head.current_a', unit: 'A', dp: 3, color: POWER_COLORS.cryoAmps },
      { label: 'Watts', key: 'amplifier.power_w',   unit: 'W', dp: 2, color: POWER_COLORS.cryoWatts },
    ],
  },
  {
    title: 'System',
    tiles: [
      { label: 'Volts',     key: 'system.voltage_v',  unit: 'V', dp: 2, color: POWER_COLORS.systemVolts },
      { label: 'Amps',      key: 'system.current_a',  unit: 'A', dp: 3, color: POWER_COLORS.systemAmps },
      { label: 'Watts',     key: 'system.power_w',    unit: 'W', dp: 3, color: POWER_COLORS.systemWatts },
      { label: 'Fan Speed', key: 'cooling.fan_speed', unit: '%', dp: 0, color: '#4dd0e1' },
    ],
  },
];

// ─── App ──────────────────────────────────────────────────────────────────────

export function App() {
  const { data, status, frameCount, onData, onFaultHistory } = useTelemetry();
  const { push, getHistory }                                  = useHistoryBuffer([...HISTORY_KEYS]);
  const { faults, loading: faultsLoading, pushUpdate }        = useFaultHistory();
  const { logout } = useSession();

  const [tick, setTick] = useState(0);
  const loading = frameCount === 0;

  // Browser-time of device boot, derived from uptime_ms on the first frame.
  // Used to convert fault `entered_ms` / `cleared_ms` (millis-since-boot) into
  // chart-axis timestamps regardless of NTP sync state. Set once and held
  // stable so faultOverlays keeps a stable identity across telemetry ticks.
  const [bootEpochMs, setBootEpochMs] = useState<number | null>(null);

  const handleFrame = useCallback((d: TelemetryData, ts: number) => {
    if (typeof d.system?.uptime_ms === 'number') {
      const candidate = ts - d.system.uptime_ms;
      setBootEpochMs((prev) => prev ?? candidate);
    }
    push(d, ts);
    setTick((n) => n + 1);
  }, [push]);

  useEffect(() => {
    onData(handleFrame);
  }, [onData, handleFrame]);

  useEffect(() => {
    onFaultHistory(pushUpdate);
  }, [onFaultHistory, pushUpdate]);

  const faultOverlays: ChartOverlay[] = useMemo(
    () => {
      const toMs = (epochSec: number, bootRelMs: number): number | null => {
        if (epochSec > 0)                  return epochSec * 1000;
        if (bootEpochMs && bootRelMs > 0)  return bootEpochMs + bootRelMs;
        return null;
      };
      return faults.flatMap<ChartOverlay>((f) => {
        const start = toMs(f.entered_epoch, f.entered_ms);
        if (start === null) return [];
        const end = f.active ? null : toMs(f.cleared_epoch, f.cleared_ms);
        return [{
          start,
          end,
          label: f.reason || 'Fault',
          color: f.active ? 'rgba(239,83,80,0.10)' : undefined,
        }];
      });
    },
    [faults, bootEpochMs],
  );

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
          network={data.network}
          loading={loading}
          onLogout={logout}
        />

        {/* ── Main content ───────────────────────────────────────────────── */}
        <Box sx={sx.mainContent}>

          {/* ── Connection-lost overlay ─────────────────────────────────── */}
          {!loading && status === 'disconnected' && (
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
                <StatusPanel data={data} key={tick} loading={loading} />
              </CollapsiblePanel>
              <Box sx={sx.faultHistorySpacer}>
                <CollapsiblePanel
                  title="Fault History"
                  defaultExpanded={false}
                  expanded={faults.some((f) => f.active) ? true : undefined}
                >
                  <FaultHistoryPanel faults={faults} loading={loading || faultsLoading} />
                </CollapsiblePanel>
              </Box>
            </Grid>

            {/* ── Row 1 right: quick-read numeric tiles ────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 6, lg: 6 }}>
              <CollapsiblePanel title="Quick Read">
                <QuickRead
                  groups={TILE_GROUPS}
                  data={data}
                  trend={getHistory}
                  windowMs={HISTORY_WINDOW_MS}
                  loading={loading}
                />
              </CollapsiblePanel>
            </Grid>

            {/* ── Row 2: Main line charts ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cold Head Temperature">
                <TemperatureChart
                  actualC={getHistory('cold_head.temp_c')}
                  ambientC={getHistory('cold_head.ambient_temp_c')}
                  targetC={getHistory('cold_head.target_temp_c')}
                  overlays={faultOverlays}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cryocooler Power">
                <TelemetryLineChart
                  title=""
                  series={[
                    { label: 'Volts', data: getHistory('cold_head.voltage_v'), color: POWER_COLORS.cryoVolts },
                    { label: 'Amps',  data: getHistory('cold_head.current_a'), color: POWER_COLORS.cryoAmps },
                    { label: 'Watts', data: getHistory('amplifier.power_w'),   color: POWER_COLORS.cryoWatts },
                  ]}
                  overlays={faultOverlays}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="System Power">
                <TelemetryLineChart
                  title=""
                  series={[
                    { label: 'Volts', data: getHistory('system.voltage_v'), color: POWER_COLORS.systemVolts },
                    { label: 'Amps',  data: getHistory('system.current_a'), color: POWER_COLORS.systemAmps },
                    { label: 'Watts', data: getHistory('system.power_w'),   color: POWER_COLORS.systemWatts },
                  ]}
                  overlays={faultOverlays}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cooling System">
                <CoolingChart
                  fanSpeed={getHistory('cooling.fan_speed')}
                  coolantTemp={getHistory('cooling.temp_c')}
                  flowRate={getHistory('cooling.flow_rate_lpm')}
                  overlays={faultOverlays}
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
                <ConsoleLog logEpoch={data.log_epoch} loading={loading} />
              </CollapsiblePanel>
            </Grid>

          </Grid>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
