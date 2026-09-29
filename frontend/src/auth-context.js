import { createContext, useContext } from "react";

export const AuthContext = createContext({ user: null });
export function useAuth() {
  const { user } = useContext(AuthContext);
  return { user, isAdmin: user?.role === "admin", canOperate: user?.role === "admin" || user?.role === "operator" };
}
