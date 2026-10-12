import type { Role } from "../types/auth";

const labels: Record<Role, string> = {
  ATTENDEE: "Attendee",
  ORGANIZER: "Event Organizer",
  STAFF: "Event Staff",
  ADMIN: "System Administrator",
};

export function roleLabel(role: Role): string {
  return labels[role];
}

export function hasRole(userRoles: Role[], requiredRole: Role): boolean {
  return userRoles.includes(requiredRole);
}
