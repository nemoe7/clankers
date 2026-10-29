/**
 * Relative timestamp formatting and periodic DOM timer (`nuu` relative-timestamps recipe).
 */

export function relativeTime(
  value,
  { compact = false, includeSeconds = false, now = Date.now() } = {}
) {
  const stamp =
    value instanceof Date ? value.getTime() : new Date(value).getTime();
  if (Number.isNaN(stamp)) {
    return compact ? "now" : "just now";
  }
  const seconds = Math.max(0, Math.floor((now - stamp) / 1000));
  if (includeSeconds) {
    if (seconds < 1) return compact ? "now" : "just now";
    if (seconds < 60) {
      return compact
        ? `${seconds}s ago`
        : seconds === 1
          ? "a second ago"
          : `${seconds} seconds ago`;
    }
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 1) return compact ? "now" : "just now";
  if (minutes < 60) {
    return compact
      ? `${minutes}min ago`
      : minutes === 1
        ? "a minute ago"
        : `${minutes} minutes ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return compact
      ? `${hours}h ago`
      : hours === 1
        ? "an hour ago"
        : `${hours} hours ago`;
  }
  const days = Math.floor(hours / 24);
  if (days < 7) {
    return compact
      ? `${days}d ago`
      : days === 1
        ? "yesterday"
        : `${days} days ago`;
  }
  if (days < 30) {
    const weeks = Math.floor(days / 7);
    return compact
      ? `${weeks}wk ago`
      : weeks === 1
        ? "last week"
        : `${weeks} weeks ago`;
  }
  if (days < 365) {
    const months = Math.max(1, Math.floor(days / 30));
    return compact
      ? `${months}mo ago`
      : months === 1
        ? "last month"
        : `${months} months ago`;
  }
  const years = Math.max(1, Math.floor(days / 365));
  return compact
    ? `${years}yr ago`
    : years === 1
      ? "last year"
      : `${years} years ago`;
}

export function mountRelativeTimers(root = document) {
  const selector = "[data-timestamp], time[datetime]";
  const nodes = [
    ...(root.matches?.(selector) ? [root] : []),
    ...root.querySelectorAll(selector),
  ];
  const refresh = () => {
    const now = Date.now();
    for (const node of nodes) {
      const value =
        node.getAttribute("data-timestamp") || node.getAttribute("datetime");
      if (!value) continue;
      const stamp = new Date(value);
      if (Number.isNaN(stamp.getTime())) continue;
      node.textContent = relativeTime(stamp, {
        compact: node.getAttribute("data-compact") === "true",
        includeSeconds: node.getAttribute("data-include-seconds") === "true",
        now,
      });
      node.title = stamp.toLocaleString();
    }
  };
  refresh();
  if (!nodes.length) return () => {};
  const interval = nodes.some(
    (node) => node.getAttribute("data-include-seconds") === "true"
  )
    ? 1000
    : 15000;
  const timer = setInterval(refresh, interval);
  return () => clearInterval(timer);
}
