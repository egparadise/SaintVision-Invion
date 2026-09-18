import type {DesktopWindow} from '@/contracts/virtualFabric';

/** Storage holds presentation preferences only. Application identity comes from code. */
export function restoreDesktopLayout(raw: string | null, defaults: DesktopWindow[], width = 1280, height = 800): DesktopWindow[] {
  const fallback = () => defaults.map(item => ({...item, position: {...item.position}, size: {...item.size}}));
  if (!raw || raw.length > 32768) return fallback();
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { return fallback(); }
  if (!Array.isArray(parsed) || parsed.length > defaults.length) return fallback();
  const viewportWidth = Number.isFinite(width) ? Math.max(320, width) : 1280;
  const viewportHeight = Number.isFinite(height) ? Math.max(240, height) : 800;
  const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
  return defaults.map((item, index) => {
    const matches = parsed.filter(row => row && typeof row === 'object' && row.id === item.id);
    const saved = matches.length === 1 ? matches[0] : undefined;
    if (!saved || saved.appId !== item.appId || !saved.position || !saved.size
      || ![saved.isOpen, saved.isMinimized, saved.isMaximized].every(value => typeof value === 'boolean')
      || ![saved.position.x, saved.position.y, saved.size.width, saved.size.height, saved.zIndex].every(finite)
      || saved.size.width <= 0 || saved.size.height <= 0) return {...item, position: {...item.position}, size: {...item.size}};
    return {...item, isOpen: saved.isOpen, isMinimized: saved.isMinimized, isMaximized: saved.isMaximized,
      zIndex: 10 + index,
      position: {x: Math.min(Math.max(16, saved.position.x), viewportWidth - 80), y: Math.min(Math.max(40, saved.position.y), viewportHeight - 100)},
      size: {width: Math.min(Math.max(240, saved.size.width), viewportWidth - 32), height: Math.min(Math.max(120, saved.size.height), viewportHeight - 120)}};
  });
}
