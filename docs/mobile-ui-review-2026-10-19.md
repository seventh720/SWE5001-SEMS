# Mobile UI review — 19 October 2026

> 分阶段检查记录，保留当时的版本、测试数与发布状态。当前进度以[项目进度](progress.md)和[测试覆盖情况](test-coverage.md)为准。

## Cloud verification

The merged release `170b791011ad819de72cb594f586dd0caeb0db18` was deployed to Lightsail successfully. HTTPS assets and the identity, event-catalog and admission health endpoints returned 200; each service reported UP. Anonymous admin and booking requests returned 401; the internal route returned 404. A fresh login returned `expiresIn: 3600`.

The inspection did not change business data. The database contained two users, one organization, one published event and no bookings. The public discovery endpoint returned zero visible events. Presentation data still needs to be prepared separately.

## UI changes in this working tree

- Replace the login panel's font-based asterisk with a CSS shape, preventing iOS from rendering it as a large green emoji. Hide the decoration and introductory list on phones, reduce panel spacing, and keep navigation compact.
- Align mobile dashboard section titles consistently and use matching font sizes for organizer and attendee panels. Keep narrow cards within the viewport.
- Request camera access before loading the QR decoder. Explicitly configure muted inline playback. If playback requires a gesture after permission is granted, offer Start preview without requesting a second stream. Distinguish permission, playback and scanner initialization errors; retain manual code entry.
- Share viewport-aware top-layer positioning between date calendars and custom selectors. Opening either control does not move the form below it. Panels reposition on scroll/resize, stay within viewport bounds, and scroll internally on short screens. Browsers without the Popover API retain absolute-positioned overlays.
- Give Cancel entire event and its confirmation a red-tinted destructive style. Calendar Cancel uses a lavender secondary style.

## Validation

- Frontend typecheck, production build and 96 tests passed.
- Browser inspection: actual login/registration at 390px; actual Dashboard component with local empty-data fixtures at 390px and 320px. Dashboard titles share a 20px font and the same left edge; document width does not exceed either tested viewport.
- Shared date/select components inspected in desktop, 390×844 and 844×390 viewports. Opening the desktop calendar left the following content at exactly the same vertical coordinate. Nested minute selection worked; a short landscape viewport constrained the calendar to 366px height with internal scrolling.
- Regression tests cover denied permission, delayed permission after close, device switching, background cleanup, blocked playback recovery, playback failure, nested Escape and outside-click cancellation.
- Temporary UI fixtures were removed after inspection; no fixture data was sent to cloud services.

Physical iPhone camera permission/playback must still be retested after these UI changes are deployed, including the browser used in the reported screenshot. Desktop responsive inspection does not verify iOS hardware or embedded-browser permission policy. An already denied or granted permission does not necessarily produce a new system prompt.

These UI changes are submitted on the `victor` branch for review and deployment. They are not part of the deployed merged release above; mobile camera verification should use the new release after merge and successful deployment.
