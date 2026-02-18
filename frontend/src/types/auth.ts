export interface AuthUser {
  sub: string;
  email: string;
}

export interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  isLoading: boolean;
}
