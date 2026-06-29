// Response shapes the Connections widget reads (only the fields it uses).

export interface EmailAccount {
  account_id: string;
  provider: string; // "icloud" | ...  (Gmail is a connections provider, not here)
  email: string;
  display_name: string;
  status?: string;
  has_token?: boolean;
}

export interface EmailStatusResult {
  ok: boolean;
  accounts: EmailAccount[];
}

export interface ConnectionAccount {
  account_id: string;
  provider: string;
  label?: string;
  display_name?: string;
  email?: string;
  workspace?: string;
  has_token?: boolean;
  status?: string;
}

export interface ConnectionApp {
  app_id: string;
  provider: string;
  label?: string;
  enabled?: boolean;
  scopes?: string[]; // the per-app scope ceiling; a connect may request a subset
}

export interface CatalogEntry {
  provider: string;
  label?: string;
  enabled?: boolean;
  configured?: boolean;
  connected?: boolean;
  apps?: ConnectionApp[];
  accounts?: ConnectionAccount[];
}

export interface CatalogResult {
  ok?: boolean;
  providers?: CatalogEntry[];
  entries?: CatalogEntry[];
}

export interface StartOAuthResult {
  ok?: boolean;
  authorize_url?: string;
  error?: { message?: string } | null;
}

export interface IdentityLink {
  provider: string;
  provider_subject: string;
  platform_user_id: string;
  label?: string;
  status?: string;
  verified_at?: number;
  updated_at?: number;
}

export interface IdentityLinksResult {
  ok?: boolean;
  platform_user_id?: string;
  links?: IdentityLink[];
  error?: string;
}

export interface IdentityMutationResult {
  ok?: boolean;
  link?: IdentityLink;
  error?: string;
  message?: string;
}

export interface IdentityLinkChallenge {
  challenge_id: string;
  provider: string;
  platform_user_id: string;
  status: 'pending' | 'completed' | 'expired' | string;
  created_at?: number;
  expires_at?: number;
  completed_at?: number;
  provider_subject?: string;
  label?: string;
}

export interface IdentityLinkChallengeResult {
  ok?: boolean;
  challenge?: IdentityLinkChallenge;
  platform_user_id?: string;
  claimable_by_current_user?: boolean;
  telegram_link_url?: string;
  platform_claim_url?: string;
  link?: IdentityLink;
  error?: string;
  message?: string;
}

export interface SupportedAuthenticatorProvider {
  provider: string;
  label?: string;
  implemented?: boolean;
  secret_label?: string;
  subject_namespace?: string;
  proofs?: string[];
}

export interface AuthenticatorRow {
  authenticator_id: string;
  provider: string;
  authority_id?: string;
  integration_id?: string;
  connection_id?: string;
  label?: string;
  enabled?: boolean;
  role_providing?: boolean;
  implemented?: boolean;
  where?: string;
  source?: 'config' | 'postgres' | string;
  subject_namespace?: string;
  secret_ref?: string;
  secret_configured?: boolean;
  selector?: Record<string, unknown>;
  verifier?: Record<string, unknown>;
  properties?: Record<string, unknown>;
}

export interface AuthenticatorsListResult {
  ok?: boolean;
  items?: AuthenticatorRow[];
  count?: number;
  providers?: string[];
  supported_providers?: SupportedAuthenticatorProvider[];
  error?: string;
  message?: string;
}

export interface AuthenticatorMutationResult {
  ok?: boolean;
  authenticator?: AuthenticatorRow;
  removed?: boolean;
  error?: string;
  message?: string;
}
