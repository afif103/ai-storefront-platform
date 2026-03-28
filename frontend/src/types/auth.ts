export interface AuthUser {
  sub: string;
  email: string;
}

export interface BootstrapUser {
  id: string;
  email: string;
  full_name: string | null;
}

export interface BootstrapMembership {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  role: string;
}

export interface BootstrapPayload {
  user: BootstrapUser;
  memberships: BootstrapMembership[];
  pending_invitations: number;
  needs_onboarding: boolean;
}

export interface LoginResponse extends BootstrapPayload {
  access_token: string;
}

export interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  bootstrap: BootstrapPayload | null;
  isLoading: boolean;
}
