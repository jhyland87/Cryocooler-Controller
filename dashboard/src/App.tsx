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
import { useHistoryBuffer } from './hooks/useHistoryBuffer';
import { useRunHistory } from './hooks/useRunHistory';
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
import { HistoryRangeToggle, rangeWindowMs } from './components/HistoryRangeToggle';
import type { TelemetryData } from './types/telemetry';
import type { ChartOverlay, HistoryRangeId, TileGroup } from './types/components';

// ─── History buffer keys ──────────────────────────────────────────────────────

const HISTORY_KEYS = [
  'cold_head.temp_c',
  'cold_head.ambient_temp_c',
  'cold_head.target_temp_c',
  'cold_head.voltage_v',
  'cold_head.current_a',
  'amplifier.power_w',
  'amplifier.active_power_w',
  'amplifier.power_factor',
  'amplifier.back_emf_v',
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
  'cold_head.cooldown_pct',
  'cold_head.delta_below_ambient_c',
  'amplifier.voltage_v',
  'amplifier.current_a',
  'system.power_w',
  'imu.roll_deg',
  'imu.pitch_deg',
  'imu.yaw_deg',
  'imu.temp_c',
  'cooling.fan_rpm',
  'cooling.pump_speed',
  'cooling.pump_rpm',
  'network.rssi_dbm',
] as const;

/** Bucket limit for line charts (≤ 2 points per bucket, about one per pixel). */
const CHART_BUCKETS = 600;

/** Bucket limit for the Quick Read tile trends (tiles are about 100 px wide). */
const TILE_BUCKETS = 60;

/** Points shown in sparklines (100 s at 1 Hz). */
const SPARK_POINTS = 100;

// ─── Quick-read tile data ─────────────────────────────────────────────────────

/** Line / tile colours shared by the Quick Read tiles and the power charts. */
const POWER_COLORS = {
  cryoVolts:   '#ce93d8',
  cryoAmps:    '#f48fb1',
  cryoWatts:   '#ef5350',
  cryoVoltAmps: '#ffab91',
  cryoPowerFactor: '#b39ddb',
  cryoBackEmf: '#dce775',
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
      { label: 'Watts', key: 'amplifier.active_power_w', unit: 'W',  dp: 2, color: POWER_COLORS.cryoWatts },
      { label: 'VA',    key: 'amplifier.power_w',        unit: 'VA', dp: 2, color: POWER_COLORS.cryoVoltAmps },
      { label: 'PF',    key: 'amplifier.power_factor',   unit: '',   dp: 3, color: POWER_COLORS.cryoPowerFactor },
      { label: 'Back-EMF', key: 'amplifier.back_emf_v',  unit: 'V',  dp: 2, color: POWER_COLORS.cryoBackEmf },
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
  const { data, status, frameCount, connectionCount, onData, onFaultHistory } = useTelemetry();
  const history                                        = useHistoryBuffer(HISTORY_KEYS);
  const { faults, loading: faultsLoading, pushUpdate } = useFaultHistory();
  const { logout } = useSession();

  const [tick, setTick] = useState(0);
  const [range, setRange] = useState<HistoryRangeId>('2m');
  const windowMs = rangeWindowMs(range);
  const loading = frameCount === 0;

  // Wall-clock time of device boot, from the history store. Converts fault
  // `entered_ms` / `cleared_ms` (millis-since-boot) into chart-axis timestamps
  // regardless of NTP sync state. It only moves on a reboot or NTP clock step,
  // so faultOverlays keeps a stable identity across telemetry ticks.
  const [bootEpochMs, setBootEpochMs] = useState<number | null>(null);

  const bumpTick = useCallback(() => setTick((n) => n + 1), []);

  const handleFrame = useCallback((d: TelemetryData, ts: number) => {
    history.push(d, ts);
    setBootEpochMs(history.clockOffsetMs ?? null);
    bumpTick();
  }, [history, bumpTick]);

  // Whole-run history recorded on the device, loaded on every (re)connect.
  useRunHistory(history, connectionCount, bumpTick);

  const series = (key: string) => history.getSeries(key, windowMs, CHART_BUCKETS);
  const recent = (key: string) => history.getRecent(key, SPARK_POINTS);
  const tileTrend = (key: string) => history.getSeries(key, windowMs, TILE_BUCKETS);

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
                  trend={tileTrend}
                  windowMs={windowMs}
                  loading={loading}
                />
              </CollapsiblePanel>
            </Grid>

            {/* ── Row 2: Main line charts ───────────────────────────────── */}
            <Grid size={{ xs: 12 }}>
              <HistoryRangeToggle value={range} onChange={setRange} spanMs={history.spanMs} />
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cold Head Temperature">
                <TemperatureChart
                  actualC={series('cold_head.temp_c')}
                  ambientC={series('cold_head.ambient_temp_c')}
                  targetC={series('cold_head.target_temp_c')}
                  overlays={faultOverlays}
                  windowMs={windowMs}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cryocooler Power">
                <TelemetryLineChart
                  title=""
                  series={[
                    { label: 'Volts', data: series('cold_head.voltage_v'), color: POWER_COLORS.cryoVolts },
                    { label: 'Amps',  data: series('cold_head.current_a'), color: POWER_COLORS.cryoAmps },
                    { label: 'Watts', data: series('amplifier.active_power_w'), color: POWER_COLORS.cryoWatts },
                    { label: 'VA',    data: series('amplifier.power_w'),        color: POWER_COLORS.cryoVoltAmps },
                    { label: 'Back-EMF', data: series('amplifier.back_emf_v'),  color: POWER_COLORS.cryoBackEmf },
                  ]}
                  overlays={faultOverlays}
                  windowMs={windowMs}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="System Power">
                <TelemetryLineChart
                  title=""
                  series={[
                    { label: 'Volts', data: series('system.voltage_v'), color: POWER_COLORS.systemVolts },
                    { label: 'Amps',  data: series('system.current_a'), color: POWER_COLORS.systemAmps },
                    { label: 'Watts', data: series('system.power_w'),   color: POWER_COLORS.systemWatts },
                  ]}
                  overlays={faultOverlays}
                  windowMs={windowMs}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <CollapsiblePanel title="Cooling System">
                <CoolingChart
                  fanSpeed={series('cooling.fan_speed')}
                  coolantTemp={series('cooling.temp_c')}
                  flowRate={series('cooling.flow_rate_lpm')}
                  overlays={faultOverlays}
                  windowMs={windowMs}
                />
              </CollapsiblePanel>
            </Grid>

            {/* ── Row 3: Sparkline panels ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 7 }}>
              <CollapsiblePanel title="Accelerometer">
                <AccelSparklines
                  accelX={recent('imu.x')}
                  accelY={recent('imu.y')}
                  accelZ={recent('imu.z')}
                  accelMag={recent('imu.accel_mag')}
                  freqHz={recent('imu.freq_hz')}
                  motion={typeof data.imu?.motion === 'number' ? data.imu.motion : undefined}
                />
              </CollapsiblePanel>
            </Grid>

            <Grid size={{ xs: 12, md: 5 }}>
              <CollapsiblePanel title="System Resources">
                <SystemSparklines
                  cpuUsage={recent('system.cpu_usage_percent')}
                  heapUsage={recent('system.heap_usage_percent')}
                  psramUsage={recent('system.psram_usage_percent')}
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
