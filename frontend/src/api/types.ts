export type AuthUser = {
  id: string;
  name: string;
  email: string;
};

export type AuthTokenResponse = {
  user: AuthUser;
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type ApiErrorDetail =
  | string
  | {
      field: string | null;
      code: string;
      message: string;
    };

export type ApiErrorBody = {
  detail?: ApiErrorDetail;
};
