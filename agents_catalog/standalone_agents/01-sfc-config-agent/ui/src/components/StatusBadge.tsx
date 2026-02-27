interface Props {
  status: string;
}

const MAP: Record<string, string> = {
  // Launch package statuses
  READY: "badge-ok",
  PROVISIONING: "badge-info",
  ERROR: "badge-error",
  // Config raw DDB status
  active: "badge-ok",
  archived: "badge-muted",
  // Config derived display statuses
  focused: "badge-sky",
  deployed: "badge-teal",
  unused: "badge-muted",
};

export default function StatusBadge({ status }: Props) {
  const cls = MAP[status] ?? "badge-muted";
  return <span className={`badge ${cls}`}>{status}</span>;
}