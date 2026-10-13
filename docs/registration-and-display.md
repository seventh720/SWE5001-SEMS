# Registration, discovery and presentation

## Implemented scope

Catalog owns category, card theme and requested registration fields. Admission validates against the authenticated published-event snapshot before reserving inventory and stores the normalized contact information and custom question label on the order. No cross-schema queries or foreign keys were added. Publication already prevents editing, so requirements cannot change underneath confirmed bookings.

One booking contains one contact form for all of its places. Supported fields are full name, contact email, phone, student ID, passport number and one custom answer. Organizers explicitly opt into each requirement; empty defaults collect no personal information. Unrequested fields are rejected and requested fields are mandatory. Limits and email validation are enforced on the server. This increment originally excluded saved profiles and advance registrations; these are now implemented in [the next increment](pre-registration-increment.md), with explicit profile application and manual booking confirmation.

Same-user/request-key comparison includes normalized information. A changed payload returns 409; retries after ambiguous responses use the same saved data. Pending submissions are retained in tab session storage until success, a definitive rejection or sign-out, and are not synced to a profile. The application does not log their contents. The attendee's own booking and the owning organizer's paginated registration list expose the information; anonymous users, other attendees and other organizers do not. The organizer endpoint omits ticket credentials and user account details. Both private APIs prohibit caching. No export/bulk download is implemented.

Category values: GENERAL, TECH, EDUCATION, MUSIC, SPORT, ART, COMMUNITY. Theme values: LILAC, LIME, PEACH, SKY. Categories determine filtering; themes only affect artwork. Category filtering is applied before pagination and combines with literal title search. No image uploads, external asset dependencies or automatic translations are introduced.

## English controls and time semantics

The shared DateTimeField renders an English month/day calendar, hour/minute selectors, Apply/Cancel and a text-entry fallback. Select renders an application-owned listbox with arrow/Home/End/Escape controls and focus return. Browser-native date/time/select pickers are not used. Time conversion and display use Singapore time (UTC+08:00) explicitly, regardless of browser locale/timezone. Backend timestamps remain UTC. Existing events keep the same instant; users outside Singapore now see the explicit Singapore wall time rather than their device wall time.

Tests cover leap days, invalid dates, month-end clamping, overnight UTC conversion, end/start ranges, locked dates and keyboard selection. Artwork has low-amplitude movement; existing Pause motion and prefers-reduced-motion disable it. The background itself contains no user data and never hides the card text.

## Upgrade and compatibility

Catalog V3 adds category, card_theme and registration_requirements. Existing events default to GENERAL/LILAC and no required fields. Admission V4 adds attendee_info (empty for historical orders) and custom_field_label. No applied migration is modified. Deploy Catalog first, Admission second, then gateway and Web. Do not mix old Admission writers with new registration-required events because older writers cannot enforce those requirements. Image rollback does not reverse schema migrations or remove stored contacts.

## Language and theme switching: effort assessment

These are engineering estimates in person-days, including implementation and focused verification, not measured effort or commitments. Existing handwritten English text, API error messages and light-colored surfaces must be inventoried before scheduling. Both switches are optional product improvements after the required ticketing/check-in workflow and project validation.

| Option | Work | Estimate |
|---|---|---|
| Light/dark/system theme | Consolidate semantic color tokens; adapt forms, calendars, overlays, errors and card artwork; store preference and follow system changes; keep QR white/black; verify contrast, focus states and mobile views | 1.5–2.5 person-days |
| English/Chinese interface | Extract labels/help/validation/empty states into message catalogs; language selector and preference; translated dates/numbers while preserving SGT; stable API error codes and localized messages; review translations and text wrapping | 3–5 person-days |
| Both, coordinated | Share settings entry and regression/visual review, while still testing both languages in both themes | Approximately 4–6.5 person-days |

Suggested order: finish staff assignment/check-in and event cancellation; implement theme switching first if capacity remains; then UI localization. Dark mode offers a smaller bounded change but should use shared tokens, not a page-wide invert filter. The English components introduced here provide one place to localize labels later.

UI localization does not translate organizer-written titles, descriptions, custom questions or submitted registration information. Supporting bilingual event content would need a separate content model/editor and additional testing; machine translation is excluded from these estimates. API error-code work is included because translating only navigation would leave failure states inconsistently English. Neither language nor theme switching is activated by this increment.
