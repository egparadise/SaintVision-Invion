/**
 * Canonical strict ISO 8601 / RFC 3339 date-time validation guard.
 *
 * Rules enforced:
 * - String type check
 * - Regex match: YYYY-MM-DDTHH:mm:ss(.sss)?(Z|[+-]HH:mm)
 * - Calendar validity: Month 1-12, Day 1-daysInMonth (including leap years)
 * - Time validity: Hour 0-23, Minute 0-59, Second 0-60 (allowing leap seconds)
 * - Strict Timezone offset bounds: Hour 0-23, Minute 0-59 (rejects invalid offsets like +99:99, -99:99, +24:00)
 * - Parsable by Date.parse
 */
export function isValidIsoDateTime(value: unknown): boolean {
  if (typeof value !== 'string') return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|([+-])(\d{2}):(\d{2}))$/.exec(value);
  if (!match) return false;

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);
  const hour = parseInt(match[4], 10);
  const minute = parseInt(match[5], 10);
  const second = parseInt(match[6], 10);

  if (month < 1 || month > 12) return false;
  if (day < 1 || day > 31) return false;
  if (hour < 0 || hour > 23) return false;
  if (minute < 0 || minute > 59) return false;
  if (second < 0 || second > 60) return false;

  const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  const daysInMonth = [31, isLeapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day > daysInMonth[month - 1]) return false;

  const tzSign = match[8];
  if (tzSign && match[9] && match[10]) {
    const tzHour = parseInt(match[9], 10);
    const tzMin = parseInt(match[10], 10);
    if (tzHour < 0 || tzHour > 23 || tzMin < 0 || tzMin > 59) return false;
  }

  const d = new Date(value);
  return !isNaN(d.getTime());
}
