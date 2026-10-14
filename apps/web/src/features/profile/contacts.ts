import type { AttendeeInfo } from "../bookings/registration";
export interface SavedContact extends Omit<AttendeeInfo, "studentId" | "customAnswer"> {
  id: string;
  label: string;
  version: number;
}
