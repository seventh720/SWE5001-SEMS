/** Vector artwork avoids iOS emoji substitution for the decorative star. */
export function Asterisk() {
  return <svg className="asterisk-icon" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
    <path d="M50 8V92M8 50H92M20 20L80 80M20 80L80 20" fill="none" stroke="currentColor" strokeWidth="12" />
  </svg>;
}
