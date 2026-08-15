/**
 * The three glyphs shadcn's components need, as inline SVG.
 *
 * ⚠ **`lucide-react` IS NOT A DEPENDENCY OF THIS PROJECT, AND THAT IS A RULING RATHER THAN AN
 * OVERSIGHT.** The eight nav icons in `templates/index.html` are inlined path data for the same
 * reason - nothing is fetched at runtime and no icon library is installed. shadcn generates
 * `select`, `checkbox` and `radio-group` with `lucide-react` imports; each is replaced by one of
 * these rather than pulling ~1MB of package for three shapes.
 *
 * **Path data is copied from Lucide, which is the same provenance the existing eight have.**
 * `static/LICENSE-icons.txt` records that notice per icon, because Lucide is ISC while icons
 * derived from Feather stay MIT under Cole Bemis's copyright - a blanket claim would be one we
 * could not support. `check` and the two chevrons are all present in Feather, so the MIT notice
 * applies to them; that file is where the record lives.
 *
 * `currentColor` throughout, so a caller's `text-*` utility decides the colour and nothing here
 * carries a palette of its own.
 */

import { cn } from "@/lib/utils";

type IconProps = React.SVGProps<SVGSVGElement>;

function Glyph({ children, className, ...props }: IconProps): React.JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={cn("size-4", className)}
      {...props}
    >
      {children}
    </svg>
  );
}

export function CheckIcon(props: IconProps): React.JSX.Element {
  return (
    <Glyph {...props}>
      <path d="M20 6 9 17l-5-5" />
    </Glyph>
  );
}

export function ChevronDownIcon(props: IconProps): React.JSX.Element {
  return (
    <Glyph {...props}>
      <path d="m6 9 6 6 6-6" />
    </Glyph>
  );
}

export function ChevronUpIcon(props: IconProps): React.JSX.Element {
  return (
    <Glyph {...props}>
      <path d="m18 15-6-6-6 6" />
    </Glyph>
  );
}
