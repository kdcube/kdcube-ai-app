export function ConnectedBadge() {
  return <span className="badge badge-ok">connected</span>;
}

export interface AccountRowProps {
  title: string;
  subtitle?: string;
  busy: boolean;
  onDisconnect: () => void;
}

export function AccountRow({ title, subtitle, busy, onDisconnect }: AccountRowProps) {
  return (
    <li className="account">
      <div className="account-info">
        <div className="account-title">
          {title} <ConnectedBadge />
        </div>
        {subtitle ? <div className="account-sub">{subtitle}</div> : null}
      </div>
      <button className="btn btn-ghost" onClick={onDisconnect} disabled={busy}>
        Disconnect
      </button>
    </li>
  );
}
