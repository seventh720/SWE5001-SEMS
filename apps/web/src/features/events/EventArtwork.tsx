import {Asterisk} from "../../shared/components/Asterisk";
export const categories = [
  ["GENERAL", "General"],
  ["TECH", "Technology"],
  ["EDUCATION", "Learning & workshops"],
  ["MUSIC", "Music"],
  ["SPORT", "Sports"],
  ["ART", "Arts & culture"],
  ["COMMUNITY", "Community"],
] as const;
export const themes = [
  ["LILAC", "Lilac"],
  ["LIME", "Lime"],
  ["PEACH", "Peach"],
  ["SKY", "Sky"],
] as const;
export function EventArtwork({
  category = "GENERAL",
  theme = "LILAC",
}: {
  category?: string;
  theme?: string;
}) {
  const index = Math.max(
    0,
    categories.findIndex((c) => c[0] === category),
  );
  const selected = themes.some((t) => t[0] === theme)
    ? theme.toLowerCase()
    : "lilac";
  return (
    <div
      className={`event-artwork theme-${selected} category-${category.toLowerCase()}`}
    >
      <div className="artwork-shapes" aria-hidden="true">
        <span className="artwork-ring" />
        <span className="artwork-glyph">
          {index === 0 ? <Asterisk/> : ["", "⌘", "◈", "♫", "↗", "✺", "◎"][index]}
        </span>
        <span className="artwork-disc" />
        <span className="artwork-word">
          {
            [
              "GET TOGETHER",
              "BUILD & INNOVATE",
              "LEARN SOMETHING",
              "FEEL THE MUSIC",
              "GET MOVING",
              "CREATE & INSPIRE",
              "FIND YOUR PEOPLE",
            ][index]
          }
        </span>
      </div>
      <span className="artwork-category">{categories[index][1]}</span>
    </div>
  );
}
