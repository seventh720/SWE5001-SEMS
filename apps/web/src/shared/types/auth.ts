export const roles = ["ATTENDEE", "ORGANIZER", "STAFF", "ADMIN"] as const;

export type Role = (typeof roles)[number];

export interface User {
  id: string;
  username: string;
  email: string;
  status: "ACTIVE" | "LOCKED" | "DISABLED";
  roles: Role[];
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  tokenType: "Bearer";
  expiresIn: number;
  user: User;
}
