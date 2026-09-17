export function timestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
export function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}
export function cell(value: unknown) {
  return value === null
    ? "NULL"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
}
