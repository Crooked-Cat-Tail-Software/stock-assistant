import { useEffect, useState } from "react";
import { useApi } from "../api/ApiContext";

type Status = "checking" | "ok" | "down";

const LABELS: Record<Status, string> = {
  checking: "Checking…",
  ok: "Online",
  down: "Backend unavailable",
};

export function HealthBadge() {
  const api = useApi();
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    api
      .getHealth()
      .then((h) => !cancelled && setStatus(h.status === "ok" ? "ok" : "down"))
      .catch(() => !cancelled && setStatus("down"));
    return () => {
      cancelled = true;
    };
  }, [api]);

  return (
    <span className={`health health--${status}`} role="status">
      <span className="health__dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  );
}
