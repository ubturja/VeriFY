import { useEffect, useState } from "react";
import { api, type MailboxProfile } from "../api";
import { useAuth } from "../auth";

function initials(email: string): string {
  const local = email.split("@")[0] || email;
  const parts = local.split(/[.\-_]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return local.slice(0, 2).toUpperCase();
}

export function ProfilePage() {
  const { session } = useAuth();
  const [profile, setProfile] = useState<MailboxProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setProfile)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load profile"));
  }, []);

  const email = profile?.email || session?.email || "";
  const role = profile?.role || session?.role || "supervisor";

  return (
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <div>
        <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">Account</p>
        <h2 className="text-3xl font-display text-[#f0ebe9]">Profile</h2>
      </div>

      {error ? <p className="text-[#e5997e] font-mono text-xs">{error}</p> : null}

      <div className="flex items-center gap-6 card-glass rounded-xl p-6 relative overflow-hidden">
        <div className="w-16 h-16 rounded-full flex items-center justify-center text-xl font-semibold z-10 glow-crimson"
          style={{ background: "linear-gradient(135deg, #8e3b31, #b8963a)", color: "#f0ebe9" }}>
          {email ? initials(email) : "?"}
        </div>
        <div className="z-10 min-w-0">
          <p className="text-lg font-semibold text-[#f0ebe9] truncate">{email || "Signed out"}</p>
          <div className="mt-2 inline-block px-2 py-0.5 rounded text-xs font-mono capitalize"
            style={{ background: "rgba(229,207,128,0.12)", color: "#e5cf80", border: "1px solid rgba(229,207,128,0.3)" }}>
            {role}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card-glass rounded-xl p-6 space-y-3">
          <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">Mailbox</p>
          {[
            ["IMAP", profile?.imap_ready ? "Ready" : "Not connected"],
            ["Last sign-in", profile?.last_login_at ? profile.last_login_at.replace("T", " ").replace("Z", " UTC") : "Not recorded"],
            ["Last poll", profile?.poll?.last_at ? profile.poll.last_at.replace("T", " ").replace("Z", " UTC") : "Not yet"],
            ["Last ingest", profile ? String(profile.poll?.ingested ?? 0) : "0"],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between items-center gap-4 py-2 border-b border-[rgba(142,59,49,0.12)]">
              <span className="text-sm text-[#8a7470]">{label}</span>
              <span className="text-sm font-mono text-[#e5cf80] text-right">{value}</span>
            </div>
          ))}
        </div>

        <div className="card-glass rounded-xl p-6 space-y-3">
          <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">Role</p>
          <p className="text-sm text-[#f0ebe9] leading-relaxed">
            The mailbox owner starts as supervisor. Switch to reviewer or auditor from the navigation menu. Auditors can read cases and cannot confirm, correct, or edit policy.
          </p>
          {profile?.poll?.error ? (
            <p className="text-xs font-mono text-[#e5997e] break-words">{profile.poll.error}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
