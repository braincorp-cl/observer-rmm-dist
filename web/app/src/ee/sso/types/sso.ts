import { User } from "@/types/accounts";
export interface SSOProvider {
  id: number;
  name: string;
  provider_id: string;
  client_id: string;
  secret: string;
  server_url: string;
  role: number | null;
}

export interface SSOAccount {
  uid: string;
  display: string;
  provider: string;
  last_login: string;
  date_joined: string;
}

export interface SSOUser extends User {
  social_accounts: SSOAccount[];
}

export interface SSOSettingsType {
  sso_enabled: boolean;
  block_local_user_logon: boolean;
}
