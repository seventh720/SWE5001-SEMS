import { describe, expect, it } from "vitest";
import { hasRole, roleLabel } from "./roles";

describe("role helpers", () => {
  it("recognizes an assigned role", () => {
    expect(hasRole(["ATTENDEE", "ORGANIZER"], "ORGANIZER")).toBe(true);
    expect(hasRole(["ATTENDEE"], "ADMIN")).toBe(false);
  });

  it("returns a readable role label", () => {
    expect(roleLabel("STAFF")).toBe("Event Staff");
  });
});
