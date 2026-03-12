import { AxisValueFormatterContext } from '@mui/x-charts/models/axis';

/**
 * Creates a stateful formatter that shows HH:mm:ss for the first tick
 * and when the hour changes, otherwise shows mm:ss.
 */
export const createTimeFormatter = () => {
  let lastHourShown: number | null = null;

  return (ms: number, context: AxisValueFormatterContext) => {
    const date = new Date(ms);
    const currentHour = date.getUTCHours();

    // Always show full time for tooltips/legends
    if (context.location !== 'tick') {
      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'UTC'
      });
    }

    // Logic for axis ticks
    if (lastHourShown === null || currentHour !== lastHourShown) {
      lastHourShown = currentHour;
      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'UTC'
      });
    }

    return date.toLocaleTimeString([], {
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'UTC'
    });
  };
};
