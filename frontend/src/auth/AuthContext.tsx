import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  getAdminToken,
  getUserToken,
  setAdminToken,
  setUserToken,
} from "../api/client";
import type { TokenResponse, UserProfile } from "../types";

interface AuthContextValue {
  userToken: string | null;
  adminToken: string | null;
  profile: UserProfile | null;
  isUser: boolean;
  isAdmin: boolean;
  login: (identifier: string, password: string) => Promise<boolean>;
  adminLogin: (username: string, password: string) => Promise<void>;
  activateProfile: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  adminLogout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [userToken, setUserTokenState] = useState<string | null>(getUserToken());
  const [adminToken, setAdminTokenState] = useState<string | null>(getAdminToken());
  const [profile, setProfile] = useState<UserProfile | null>(null);

  const refreshProfile = useCallback(async () => {
    if (!getUserToken()) {
      setProfile(null);
      return;
    }
    try {
      const me = await api<UserProfile>("/users/me");
      setProfile(me);
    } catch {
      setProfile(null);
    }
  }, []);

  const login = useCallback(
    async (identifier: string, password: string): Promise<boolean> => {
      const res = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: { identifier, password },
      });
      setUserToken(res.access_token);
      setUserTokenState(res.access_token);
      await refreshProfile();
      return res.must_change_password;
    },
    [refreshProfile]
  );

  const adminLogin = useCallback(
    async (username: string, password: string): Promise<void> => {
      const res = await api<TokenResponse>("/auth/admin/login", {
        method: "POST",
        admin: true,
        body: { username, password },
      });
      setAdminToken(res.access_token);
      setAdminTokenState(res.access_token);
    },
    []
  );

  const activateProfile = useCallback(
    async (name: string, email: string, password: string): Promise<void> => {
      const res = await api<TokenResponse>("/auth/activate-profile", {
        method: "POST",
        body: { name, email, password },
      });
      setUserToken(res.access_token);
      setUserTokenState(res.access_token);
      await refreshProfile();
    },
    [refreshProfile]
  );

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* token may already be invalid */
    }
    setUserToken(null);
    setUserTokenState(null);
    setProfile(null);
  }, []);

  const adminLogout = useCallback(() => {
    setAdminToken(null);
    setAdminTokenState(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      userToken,
      adminToken,
      profile,
      isUser: !!userToken,
      isAdmin: !!adminToken,
      login,
      adminLogin,
      activateProfile,
      logout,
      adminLogout,
      refreshProfile,
    }),
    [userToken, adminToken, profile, login, adminLogin, activateProfile, logout, adminLogout, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}