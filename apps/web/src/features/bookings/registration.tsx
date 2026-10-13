export interface Requirements {
  realName: boolean;
  email: boolean;
  phone: boolean;
  studentId: boolean;
  passport: boolean;
  customFieldLabel: string | null;
}
export const noRequirements: Requirements = {
  realName: false,
  email: false,
  phone: false,
  studentId: false,
  passport: false,
  customFieldLabel: null,
};
export interface AttendeeInfo {
  realName?: string | null;
  email?: string | null;
  phone?: string | null;
  studentId?: string | null;
  passportNumber?: string | null;
  customAnswer?: string | null;
}
export const registrationFields = [
  {
    rule: "realName",
    key: "realName",
    label: "Full name",
    max: 100,
    type: "text",
  },
  {
    rule: "email",
    key: "email",
    label: "Contact email",
    max: 254,
    type: "email",
  },
  { rule: "phone", key: "phone", label: "Phone number", max: 40, type: "tel" },
  {
    rule: "studentId",
    key: "studentId",
    label: "Student ID",
    max: 100,
    type: "text",
  },
  {
    rule: "passport",
    key: "passportNumber",
    label: "Passport number",
    max: 100,
    type: "text",
  },
] as const;
export function RegistrationSummary({
  info,
  customFieldLabel,
}: {
  info?: AttendeeInfo;
  customFieldLabel?: string | null;
}) {
  if (!info || !Object.values(info).some(Boolean))
    return <p className="muted">No registration information requested.</p>;
  return (
    <dl className="registration-summary">
      {registrationFields.map(
        (f) =>
          info[f.key] && (
            <div key={f.key}>
              <dt>{f.label}</dt>
              <dd>{info[f.key]}</dd>
            </div>
          ),
      )}
      {info.customAnswer && (
        <div>
          <dt>{customFieldLabel ?? "Event question"}</dt>
          <dd>{info.customAnswer}</dd>
        </div>
      )}
    </dl>
  );
}
