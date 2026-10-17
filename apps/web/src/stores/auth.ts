import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserInfo } from "@/lib/api";

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  setAuth: (token: string, user: UserInfo) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("sg_token", token);
          localStorage.setItem("sg_user", JSON.stringify(user));
        }
        set({ token, user });
      },
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("sg_token");
          localStorage.removeItem("sg_user");
          for (const key of Object.keys(localStorage))
            if (key.startsWith("sg-network-v2:")) localStorage.removeItem(key);
        }
        set({ token: null, user: null });
      },
    }),
    { name: "sg-auth" },
  ),
);
