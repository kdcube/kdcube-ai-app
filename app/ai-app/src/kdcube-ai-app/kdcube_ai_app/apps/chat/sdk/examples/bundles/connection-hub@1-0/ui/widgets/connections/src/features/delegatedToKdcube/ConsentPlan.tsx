import type { DelegatedToKdcubeAccount, DelegatedToKdcubeProvider } from '../../api/types';

// Shown when the user arrives from a chat consent card. Turns the deep-link
// parameters into an explicit plan: what is already in place, what still
// needs their action, and one primary button for the next step.

export interface ConsentPlanRequest {
  provider?: DelegatedToKdcubeProvider;
  providerLabel: string;
  requestedClaims: string[];
  account?: DelegatedToKdcubeAccount;
}

export type ConsentPlanAction = 'connect' | 'reconnect' | 'approve' | 'done';

export interface ConsentPlanState {
  connected: boolean;
  healthy: boolean;
  approvedClaims: string[];
  missingClaims: string[];
  action: ConsentPlanAction;
}

export function consentPlanState(request: ConsentPlanRequest): ConsentPlanState {
  const account = request.account;
  const connected = Boolean(account);
  const status = account?.credential_status || account?.status || '';
  const healthy = connected
    && !account?.reconnect_required
    && !['reconnect_required', 'missing', 'revoked'].includes(status);
  const approved = new Set(account?.claims || []);
  const approvedClaims = request.requestedClaims.filter((claim) => approved.has(claim));
  const missingClaims = request.requestedClaims.filter((claim) => !approved.has(claim));
  const action: ConsentPlanAction = !connected
    ? 'connect'
    : !healthy
      ? 'reconnect'
      : missingClaims.length
        ? 'approve'
        : 'done';
  return { connected, healthy, approvedClaims, missingClaims, action };
}

const ACTION_BUTTON: Record<Exclude<ConsentPlanAction, 'done'>, string> = {
  connect: 'Connect account',
  reconnect: 'Reconnect account',
  approve: 'Approve access',
};

interface StepProps {
  done: boolean;
  index: number;
  children: React.ReactNode;
}

function PlanStep({ done, index, children }: StepProps) {
  return (
    <li className={`plan-step${done ? ' plan-step-done' : ''}`}>
      <span className="plan-step-mark">{done ? '✓' : index}</span>
      <span className="plan-step-body">{children}</span>
    </li>
  );
}

export interface ConsentPlanProps {
  request: ConsentPlanRequest;
  claimLabel: (claimId: string) => string;
  busy: boolean;
  onAction: (action: Exclude<ConsentPlanAction, 'done'>) => void;
  onDismiss: () => void;
}

export function ConsentPlan({ request, claimLabel, busy, onAction, onDismiss }: ConsentPlanProps) {
  const state = consentPlanState(request);
  const accountName = request.account
    ? (request.account.display_name || request.account.email || request.account.workspace || request.account.account_id)
    : '';

  return (
    <div className="plan">
      <div className="plan-head">
        <div>
          <div className="form-title">A KDCube tool needs your {request.providerLabel} account</div>
          <p className="muted">
            Complete the steps below, then retry your request in chat.
          </p>
        </div>
        <button className="btn btn-ghost" type="button" onClick={onDismiss}>Dismiss</button>
      </div>
      <ol className="plan-steps">
        <PlanStep done={state.connected} index={1}>
          {state.connected
            ? <>Account connected: <strong>{accountName}</strong></>
            : <>Connect your {request.providerLabel} account</>}
        </PlanStep>
        <PlanStep done={state.connected && state.healthy} index={2}>
          {state.connected && !state.healthy
            ? <>Its stored access no longer works — reconnect it</>
            : <>Account access is working</>}
        </PlanStep>
        <PlanStep done={state.connected && state.missingClaims.length === 0} index={3}>
          <span className="plan-claims">
            Approve what the tool needs:{' '}
            {request.requestedClaims.map((claimId) => (
              <span
                key={claimId}
                className={`claim-chip${state.approvedClaims.includes(claimId) ? ' claim-chip-done' : ' claim-chip-missing'}`}
              >
                {state.approvedClaims.includes(claimId) ? '✓ ' : ''}{claimLabel(claimId)}
              </span>
            ))}
          </span>
        </PlanStep>
      </ol>
      {state.action === 'done' ? (
        <p className="notice success">All set — go back to chat and retry your request.</p>
      ) : (
        <button className="btn" type="button" disabled={busy} onClick={() => onAction(state.action as Exclude<ConsentPlanAction, 'done'>)}>
          {ACTION_BUTTON[state.action as Exclude<ConsentPlanAction, 'done'>]}
        </button>
      )}
    </div>
  );
}
