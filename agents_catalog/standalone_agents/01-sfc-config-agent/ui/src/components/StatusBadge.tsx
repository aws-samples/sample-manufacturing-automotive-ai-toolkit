interface Props {
  status: string;
}

const MAP: Record<string, string> = {
  READY: "badge-ok",
  PROVISIONING: "badge-info",
  ERROR: "badge-error",
  active: "badge-ok",
  archived: "badge-muted",
};

export default function StatusBadge({ status }: Props) {
  const cls = MAP[status] ?? "badge-muted";
  return <span className={`badge ${cls}`}>{status}</span>;
}