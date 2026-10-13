export function validDateTime(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return false;
  const date = new Date(`${value}:00Z`);
  return (
    Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 16) === value &&
    Number(value.slice(0, 4)) >= 1900
  );
}
export function toInstant(value: string) {
  if (!validDateTime(value))
    throw new Error("Enter a valid date and time: YYYY-MM-DD HH:mm.");
  return new Date(`${value}:00+08:00`).toISOString();
}
export function singaporeInput(value: string) {
  return new Date(Date.parse(value) + 8 * 3600000).toISOString().slice(0, 16);
}
export function formatDateTime(value: string) {
  return (
    new Intl.DateTimeFormat("en-SG", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Singapore",
      hourCycle: "h23",
    }).format(new Date(value)) + " SGT"
  );
}
