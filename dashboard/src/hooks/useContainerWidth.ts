import { useRef, useState, useEffect } from 'preact/hooks';

/**
 * Observes the width of a container element via ResizeObserver and returns
 * both a ref to attach to the element and the current measured width in pixels.
 *
 * Falls back to 400 px until the first observation fires.
 *
 * Usage:
 *   const [containerRef, width] = useContainerWidth<HTMLDivElement>();
 *   return <div ref={containerRef}>...</div>;
 */
export function useContainerWidth<T extends HTMLElement = HTMLDivElement>(): [
  React.RefObject<T>,
  number,
] {
  const ref   = useRef<T>(null);
  const [width, setWidth] = useState(400);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Seed with the element's current size before the first ResizeObserver
    // callback fires so the chart renders correctly on mount.
    setWidth(el.getBoundingClientRect().width || 400);

    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return [ref, width];
}

/**
 * Given a chart container width, returns a `tickMinStep` value in milliseconds
 * suitable for the xAxis of a LineChart showing a fixed rolling time window.
 *
 * Why tickMinStep instead of tickNumber:
 *   `tickNumber` is a hint — D3 picks the nearest "nice" interval to your
 *   requested count.  As the time window slides forward each second, the exact
 *   range changes, D3 recomputes its nice intervals, and the count can flip
 *   between adjacent values (e.g. 6 ↔ 12) every few frames.
 *
 *   `tickMinStep` pins the spacing to a fixed number of milliseconds, so ticks
 *   always land on clean absolute-time boundaries (e.g. :00, :10, :20 …).
 *   The visible count only changes when the window genuinely spans a different
 *   number of steps — which is extremely rare at 1 Hz.
 *
 * @param containerWidth  Measured outer container width (px).
 * @param windowMs        Total time window shown (ms). Default 60 000 (60 s at 1 Hz).
 * @param margins         Combined left + right chart margin (px). Default 62 (52 + 10).
 * @param labelWidth      Estimated rendered width of one "HH:MM:SS" label (px). Default 72.
 */
export function calcTickStep(
  containerWidth: number,
  windowMs  = 60_000,
  margins   = 62,
  labelWidth = 72,
): number {
  const plotWidth  = Math.max(1, containerWidth - margins);
  const maxTicks   = Math.max(2, Math.floor(plotWidth / labelWidth));
  const rawStepMs  = windowMs / maxTicks;
  // Round up to the nearest clean boundary so ticks always land at predictable
  // wall-clock positions regardless of when the session started.
  const niceSteps  = [2_000, 5_000, 10_000, 15_000, 20_000, 30_000, 60_000];
  return niceSteps.find((s) => s >= rawStepMs) ?? 60_000;
}
