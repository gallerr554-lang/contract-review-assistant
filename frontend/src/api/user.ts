import { api } from "@/api/http";

export type UserRole = "user" | "admin";

export interface ManagedUser {
  id: number;
  email: string;
  role: UserRole;
  status: boolean;
  create_time: string;
  last_login_time: string | null;
  task_count: number;
}

export interface ManagedUserList {
  items: ManagedUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserQuery {
  keyword?: string;
  role?: UserRole;
  enabled?: boolean;
  page: number;
  page_size: number;
}

export async function listUsers(params: UserQuery) {
  const { data } = await api.get<ManagedUserList>("/users", { params });
  return data;
}

export async function getManagedUser(id: number) {
  const { data } = await api.get<ManagedUser>(`/users/${id}`);
  return data;
}

export async function setUserStatus(id: number, status: boolean) {
  const { data } = await api.patch<ManagedUser>(`/users/${id}/status`, {
    status,
    confirmed: true
  });
  return data;
}

export async function setUserRole(id: number, role: UserRole) {
  const { data } = await api.patch<ManagedUser>(`/users/${id}/role`, {
    role,
    confirmed: true
  });
  return data;
}

export async function resetUserPassword(id: number, newPassword: string) {
  const { data } = await api.post<ManagedUser>(`/users/${id}/reset-password`, {
    new_password: newPassword,
    confirmed: true
  });
  return data;
}
